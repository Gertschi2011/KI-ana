"""Block Viewer API Routes for Flask Backend"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, send_file
from pathlib import Path
import json
import hashlib
import sys
from typing import Any, Dict, List

# Add system directory to path for block_signer import
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "system"))
sys.path.insert(0, '/app/system')  # For Docker

# Import signer functions
do_sign_block = None
do_verify_block = None
SIGNER_AVAILABLE = False

try:
    from block_signer import sign_block as do_sign_block, verify_block as do_verify_block
    SIGNER_AVAILABLE = True
except Exception as e:
    print(f"Warning: Block signer not available: {e}")
    SIGNER_AVAILABLE = False

bp = Blueprint("viewer", __name__)

# Paths
# In Docker container, files are mounted at /app/memory and /app/system
PROJECT_ROOT = Path("/app")
CHAIN_DIR = PROJECT_ROOT / "memory" / "long_term" / "blocks"

def compute_hash(data: str) -> str:
    """Compute SHA256 hash of data"""
    return hashlib.sha256(data.encode('utf-8')).hexdigest()

def load_block(file_path: Path) -> Dict[str, Any] | None:
    """Load a single block from file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None

def verify_block(block: Dict[str, Any]) -> tuple[bool, bool]:
    """Verify block hash and signature
    Returns: (hash_valid, sig_valid)
    """
    try:
        # Check hash
        stored_hash = block.get('hash', '')
        content = block.get('content', '')
        
        # Content can be string or dict
        if isinstance(content, dict):
            content_str = json.dumps(content, ensure_ascii=False, separators=(',', ':'))
        else:
            content_str = str(content)
        
        computed = compute_hash(content_str)
        hash_valid = (stored_hash == computed)
        
        # Signature check using real Ed25519 verification
        sig_valid = False
        if SIGNER_AVAILABLE and block.get('signature') and block.get('pubkey'):
            try:
                sig_valid, _ = do_verify_block(block)
            except Exception:
                sig_valid = False
        else:
            # Fallback: just check if signature and pubkey exist
            sig_valid = bool(block.get('signature')) and bool(block.get('pubkey'))
        
        return (hash_valid, sig_valid)
    except Exception as e:
        return (False, False)

@bp.route('/viewer/api/blocks')
def list_blocks():
    """List all blocks with filtering and pagination"""
    try:
        # Query params
        verified_only = request.args.get('verified_only', 'true').lower() == 'true'
        query = request.args.get('q', '').lower()
        sort_by = request.args.get('sort', 'none')
        page = max(1, int(request.args.get('page', 1)))
        limit = min(100, max(1, int(request.args.get('limit', 20))))
        
        # Load all blocks
        blocks = []
        if CHAIN_DIR.exists():
            for file_path in CHAIN_DIR.glob('*.json'):
                block = load_block(file_path)
                if not block:
                    continue
                    
                # Verify
                hash_valid, sig_valid = verify_block(block)
                is_verified = hash_valid and sig_valid
                
                # Filter verified
                if verified_only and not is_verified:
                    continue
                
                # Filter by query - search in multiple fields
                if query:
                    meta = block.get('meta', {})
                    searchable = f"{block.get('title', '')} {meta.get('title', '')} {block.get('topic', '')} {meta.get('topic', '')} {block.get('source', '')} {meta.get('source', '')} {' '.join(block.get('tags', []))}".lower()
                    if query not in searchable:
                        continue
                
                # Build item - handle both old and new block formats
                # New format: fields directly in block
                # Old format: fields in meta object
                meta = block.get('meta', {})
                trust = block.get('trust', {})
                
                item = {
                    'id': block.get('id', file_path.stem),
                    'title': block.get('title', meta.get('title', '')),
                    'topic': block.get('topic', meta.get('topic', '')),
                    'source': block.get('source', meta.get('source', '')),
                    'timestamp': block.get('signed_at', block.get('ts', meta.get('timestamp', ''))),
                    'rating': meta.get('rating'),
                    'size': len(json.dumps(block)),
                    'hash': block.get('hash', ''),
                    'signature': block.get('signature', ''),
                    'pubkey': block.get('pubkey', ''),
                    'valid': hash_valid,
                    'sig_valid': sig_valid,
                    'trust': {
                        'score': trust.get('score', 0),
                        'factors': trust.get('factors', {})
                    },
                    'tags': block.get('tags', []),
                    'url': block.get('url', ''),
                    'file': str(file_path.relative_to(PROJECT_ROOT))
                }
                blocks.append(item)
        
        # Sort
        if sort_by == 'trust':
            blocks.sort(key=lambda x: x.get('trust', {}).get('score', 0), reverse=True)
        elif sort_by == 'rating':
            blocks.sort(key=lambda x: x.get('rating') or 0, reverse=True)
        elif sort_by == 'time':
            blocks.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Paginate
        total = len(blocks)
        start = (page - 1) * limit
        end = start + limit
        items = blocks[start:end]
        pages = (total + limit - 1) // limit
        
        return jsonify({
            'ok': True,
            'items': items,
            'total': total,
            'page': page,
            'pages': pages,
            'limit': limit
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@bp.route('/viewer/api/block/by-id/<block_id>')
def get_block_by_id(block_id: str):
    """Get single block by ID"""
    try:
        # Find block file
        file_path = CHAIN_DIR / f"{block_id}.json"
        if not file_path.exists():
            return jsonify({'ok': False, 'error': 'Block not found'}), 404
        
        block = load_block(file_path)
        if not block:
            return jsonify({'ok': False, 'error': 'Failed to load block'}), 500
        
        return jsonify({'ok': True, 'block': block})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@bp.route('/viewer/api/block/download')
def download_block():
    """Download block file"""
    try:
        file_param = request.args.get('file', '')
        if not file_param:
            return jsonify({'ok': False, 'error': 'file parameter required'}), 400
        
        # Security: ensure path is within CHAIN_DIR
        file_path = (PROJECT_ROOT / file_param).resolve()
        if not str(file_path).startswith(str(CHAIN_DIR)):
            return jsonify({'ok': False, 'error': 'Invalid file path'}), 403
        
        if not file_path.exists():
            return jsonify({'ok': False, 'error': 'File not found'}), 404
        
        return send_file(file_path, as_attachment=True, download_name=file_path.name)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@bp.route('/viewer/api/block/rate', methods=['POST'])
def rate_block():
    """Rate a block"""
    try:
        data = request.get_json() or {}
        block_id = data.get('id', '')
        score = data.get('score')
        
        if not block_id or score is None:
            return jsonify({'ok': False, 'error': 'id and score required'}), 400
        
        # Load block
        file_path = CHAIN_DIR / f"{block_id}.json"
        if not file_path.exists():
            return jsonify({'ok': False, 'error': 'Block not found'}), 404
        
        block = load_block(file_path)
        if not block:
            return jsonify({'ok': False, 'error': 'Failed to load block'}), 500
        
        # Update rating
        if 'meta' not in block:
            block['meta'] = {}
        block['meta']['rating'] = int(score)
        
        # Save
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(block, f, ensure_ascii=False, indent=2)
        
        return jsonify({'ok': True, 'rating': score})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@bp.route('/viewer/api/block/rehash', methods=['POST'])
def rehash_block():
    """Recompute hash for a block"""
    try:
        data = request.get_json() or {}
        file_param = data.get('file', '')
        
        if not file_param:
            return jsonify({'ok': False, 'error': 'file parameter required'}), 400
        
        # Load block
        file_path = (PROJECT_ROOT / file_param).resolve()
        if not str(file_path).startswith(str(CHAIN_DIR)):
            return jsonify({'ok': False, 'error': 'Invalid file path'}), 403
        
        if not file_path.exists():
            return jsonify({'ok': False, 'error': 'File not found'}), 404
        
        block = load_block(file_path)
        if not block:
            return jsonify({'ok': False, 'error': 'Failed to load block'}), 500
        
        # Recompute hash
        content = block.get('content', '')
        if isinstance(content, dict):
            content_str = json.dumps(content, ensure_ascii=False, separators=(',', ':'))
        else:
            content_str = str(content)
        
        new_hash = compute_hash(content_str)
        block['hash'] = new_hash
        
        # Save
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(block, f, ensure_ascii=False, indent=2)
        
        return jsonify({'ok': True, 'hash': new_hash})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@bp.route('/viewer/api/block/rehash-all', methods=['POST'])
def rehash_all_blocks():
    """Recompute hashes for all blocks"""
    try:
        checked = 0
        fixed = 0
        
        if CHAIN_DIR.exists():
            for file_path in CHAIN_DIR.glob('*.json'):
                checked += 1
                block = load_block(file_path)
                if not block:
                    continue
                
                # Check hash
                stored_hash = block.get('hash', '')
                content = block.get('content', '')
                
                if isinstance(content, dict):
                    content_str = json.dumps(content, ensure_ascii=False, separators=(',', ':'))
                else:
                    content_str = str(content)
                
                computed = compute_hash(content_str)
                
                if stored_hash != computed:
                    # Fix it
                    block['hash'] = computed
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(block, f, ensure_ascii=False, indent=2)
                    fixed += 1
        
        return jsonify({'ok': True, 'checked': checked, 'fixed': fixed})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@bp.route('/viewer/api/block/sign-all', methods=['POST'])
def sign_all_blocks():
    """Sign all blocks that don't have a valid signature"""
    try:
        if not SIGNER_AVAILABLE:
            return jsonify({'ok': False, 'error': 'Signing not available'}), 500
        
        checked = 0
        signed = 0
        
        if CHAIN_DIR.exists():
            for file_path in CHAIN_DIR.glob('*.json'):
                checked += 1
                block = load_block(file_path)
                if not block:
                    continue
                
                # Check if already has valid signature
                has_sig = bool(block.get('signature')) and bool(block.get('pubkey'))
                if has_sig:
                    try:
                        is_valid, _ = do_verify_block(block)
                        if is_valid:
                            continue  # Already signed and valid
                    except:
                        pass  # Signature invalid, re-sign
                
                # Sign the block
                try:
                    signature_b64, pubkey_b64, signed_at = do_sign_block(block)
                    block['signature'] = signature_b64
                    block['pubkey'] = pubkey_b64
                    block['signed_at'] = signed_at
                    
                    # Save
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(block, f, ensure_ascii=False, indent=2)
                    signed += 1
                except Exception:
                    continue
        
        return jsonify({'ok': True, 'checked': checked, 'signed': signed})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@bp.route('/viewer/api/blocks/health')
def blocks_health():
    """Get health status of blocks"""
    try:
        total = 0
        verified = 0
        unverified = 0
        
        if CHAIN_DIR.exists():
            for file_path in CHAIN_DIR.glob('*.json'):
                total += 1
                block = load_block(file_path)
                if block:
                    hash_valid, sig_valid = verify_block(block)
                    if hash_valid and sig_valid:
                        verified += 1
                    else:
                        unverified += 1
        
        coverage = (verified / total * 100) if total > 0 else 0
        
        # Get signer public key if available
        signer_info = {
            'valid': SIGNER_AVAILABLE,
            'key_id': 'not_available'
        }
        if SIGNER_AVAILABLE:
            try:
                from block_signer import ensure_keys
                pub_b64, _ = ensure_keys()
                signer_info['key_id'] = pub_b64[:16] + '...'  # Show first 16 chars
            except:
                pass
        
        return jsonify({
            'ok': True,
            'total': total,
            'verified': verified,
            'unverified': unverified,
            'coverage_percent': round(coverage, 1),
            'signer': signer_info
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
