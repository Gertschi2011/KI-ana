"""
Vision Processor - Image Understanding for KI_ana

Enables the AI to:
- Analyze and understand images
- Extract text from images (OCR)
- Describe image content
- Answer questions about images
"""
from __future__ import annotations
import base64
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import io


class VisionProcessor:
    """
    Vision processing system for image understanding.
    
    Uses LLaVA or similar vision-language models to understand images.
    
    Usage:
        vision = VisionProcessor()
        
        # Analyze image
        description = await vision.describe_image(image_path)
        
        # Answer question about image
        answer = await vision.answer_question(image_path, "What's in this image?")
    """
    
    def __init__(self, ollama_host: str = "http://localhost:11434"):
        self.ollama_host = ollama_host
        self.vision_model = "llava:latest"  # Or "bakllava", "llava-phi3"
        self.available = False
        self._check_availability()
    
    def _check_availability(self):
        """Check if vision model is available"""
        try:
            import requests
            response = requests.get(f"{self.ollama_host}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                self.available = any(self.vision_model in m.get("name", "") for m in models)
        except Exception:
            self.available = False
    
    def _encode_image(self, image_path: str) -> str:
        """Encode image to base64"""
        try:
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode()
        except Exception as e:
            raise Exception(f"Failed to encode image: {e}")
    
    def _encode_image_bytes(self, image_bytes: bytes) -> str:
        """Encode image bytes to base64"""
        return base64.b64encode(image_bytes).decode()
    
    async def describe_image(self, image_path: str, detail_level: str = "normal") -> Dict[str, Any]:
        """
        Generate a description of an image.
        
        Args:
            image_path: Path to image file
            detail_level: "brief", "normal", or "detailed"
            
        Returns:
            Dict with description and metadata
        """
        if not self.available:
            return {
                "success": False,
                "error": "Vision model not available. Install with: ollama pull llava"
            }
        
        try:
            import requests
            
            # Encode image
            image_b64 = self._encode_image(image_path)
            
            # Craft prompt based on detail level
            prompts = {
                "brief": "Describe this image in one sentence.",
                "normal": "Describe what you see in this image.",
                "detailed": "Provide a detailed description of this image, including objects, colors, composition, and any text visible."
            }
            prompt = prompts.get(detail_level, prompts["normal"])
            
            # Call Ollama vision API
            response = requests.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model": self.vision_model,
                    "prompt": prompt,
                    "images": [image_b64],
                    "stream": False
                },
                timeout=60
            )
            
            if response.status_code != 200:
                raise Exception(f"Ollama API error: {response.status_code}")
            
            result = response.json()
            description = result.get("response", "").strip()
            
            return {
                "success": True,
                "description": description,
                "detail_level": detail_level,
                "model": self.vision_model
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def answer_question(self, image_path: str, question: str) -> Dict[str, Any]:
        """
        Answer a question about an image.
        
        Args:
            image_path: Path to image file
            question: Question to answer
            
        Returns:
            Dict with answer and metadata
        """
        if not self.available:
            return {
                "success": False,
                "error": "Vision model not available"
            }
        
        try:
            import requests
            
            image_b64 = self._encode_image(image_path)
            
            response = requests.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model": self.vision_model,
                    "prompt": question,
                    "images": [image_b64],
                    "stream": False
                },
                timeout=60
            )
            
            if response.status_code != 200:
                raise Exception(f"Ollama API error: {response.status_code}")
            
            result = response.json()
            answer = result.get("response", "").strip()
            
            return {
                "success": True,
                "question": question,
                "answer": answer,
                "model": self.vision_model
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def extract_text_ocr(self, image_path: str) -> Dict[str, Any]:
        """
        Extract text from image using OCR.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Dict with extracted text
        """
        try:
            # Try Tesseract first (if available)
            import pytesseract
            from PIL import Image
            
            img = Image.open(image_path)
            text = pytesseract.image_to_string(img)
            
            return {
                "success": True,
                "text": text.strip(),
                "method": "tesseract"
            }
            
        except ImportError:
            # Fallback to vision model
            result = await self.answer_question(
                image_path,
                "Extract all visible text from this image. Return only the text, nothing else."
            )
            
            if result["success"]:
                return {
                    "success": True,
                    "text": result["answer"],
                    "method": "vision_model"
                }
            else:
                return result
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def classify_image(self, image_path: str, categories: List[str]) -> Dict[str, Any]:
        """
        Classify image into one of given categories.
        
        Args:
            image_path: Path to image file
            categories: List of possible categories
            
        Returns:
            Dict with classification result
        """
        if not categories:
            return {"success": False, "error": "No categories provided"}
        
        question = f"This image shows one of these: {', '.join(categories)}. Which one is it? Answer with only the category name."
        
        result = await self.answer_question(image_path, question)
        
        if result["success"]:
            # Try to match answer to categories
            answer_lower = result["answer"].lower()
            matched_category = None
            
            for cat in categories:
                if cat.lower() in answer_lower:
                    matched_category = cat
                    break
            
            result["category"] = matched_category or result["answer"]
            result["confidence"] = "high" if matched_category else "low"
        
        return result
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get vision processor statistics"""
        return {
            "available": self.available,
            "model": self.vision_model if self.available else None,
            "ollama_host": self.ollama_host
        }


# Global instance
_vision_processor_instance: Optional[VisionProcessor] = None


def get_vision_processor() -> VisionProcessor:
    """Get or create global VisionProcessor instance"""
    global _vision_processor_instance
    if _vision_processor_instance is None:
        import os
        ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        _vision_processor_instance = VisionProcessor(ollama_host)
    return _vision_processor_instance


if __name__ == "__main__":
    # Self-test
    import asyncio
    
    print("=== Vision Processor Self-Test ===\n")
    
    async def test():
        vision = VisionProcessor()
        stats = vision.get_statistics()
        
        print(f"Vision available: {stats['available']}")
        if stats['available']:
            print(f"Model: {stats['model']}")
        else:
            print("⚠️  Install vision model: ollama pull llava")
        
        print("\n✅ Vision Processor initialized!")
    
    asyncio.run(test())
