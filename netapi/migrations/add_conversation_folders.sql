-- Migration: Add conversation folders
-- Created: 2025-10-29

-- Create conversation_folders table
CREATE TABLE IF NOT EXISTS conversation_folders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    color VARCHAR(7) DEFAULT '#667eea',
    icon VARCHAR(10) DEFAULT '📁',
    sort_order INTEGER DEFAULT 0,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    UNIQUE(user_id, name)
);

-- Add folder_id to conversations
ALTER TABLE conversations 
ADD COLUMN IF NOT EXISTS folder_id INTEGER REFERENCES conversation_folders(id) ON DELETE SET NULL;

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_conversations_folder ON conversations(folder_id);
CREATE INDEX IF NOT EXISTS idx_folders_user ON conversation_folders(user_id);

-- Insert default folders for existing users
INSERT INTO conversation_folders (user_id, name, icon, sort_order, created_at, updated_at)
SELECT 
    id,
    'Allgemein',
    '💬',
    0,
    EXTRACT(EPOCH FROM NOW())::INTEGER,
    EXTRACT(EPOCH FROM NOW())::INTEGER
FROM users
WHERE NOT EXISTS (
    SELECT 1 FROM conversation_folders 
    WHERE conversation_folders.user_id = users.id 
    AND conversation_folders.name = 'Allgemein'
)
ON CONFLICT (user_id, name) DO NOTHING;
