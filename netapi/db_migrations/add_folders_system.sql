-- Migration: Add Folders System
-- Date: 2025-11-04
-- Description: Adds folder organization for conversations

-- Create folders table
CREATE TABLE IF NOT EXISTS folders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    color VARCHAR(20) DEFAULT '#667eea',
    icon VARCHAR(10) DEFAULT '📁',
    position INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_folder_per_user UNIQUE (user_id, name)
);

-- Add folder_id to conversations table
ALTER TABLE conversations 
ADD COLUMN IF NOT EXISTS folder_id INTEGER REFERENCES folders(id) ON DELETE SET NULL;

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_folders_user_id ON folders(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_folder_id ON conversations(folder_id);
CREATE INDEX IF NOT EXISTS idx_conversations_user_folder ON conversations(user_id, folder_id);

-- Create default folders for existing users
INSERT INTO folders (user_id, name, color, icon, position)
SELECT DISTINCT user_id, 'Allgemein', '#667eea', '📁', 0
FROM conversations
WHERE NOT EXISTS (
    SELECT 1 FROM folders f WHERE f.user_id = conversations.user_id AND f.name = 'Allgemein'
)
ON CONFLICT DO NOTHING;

-- Add trigger to update updated_at
CREATE OR REPLACE FUNCTION update_folder_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_folder_timestamp
    BEFORE UPDATE ON folders
    FOR EACH ROW
    EXECUTE FUNCTION update_folder_timestamp();

COMMENT ON TABLE folders IS 'User-created folders for organizing conversations';
COMMENT ON COLUMN folders.position IS 'Display order in sidebar (lower = higher up)';
COMMENT ON COLUMN conversations.folder_id IS 'Optional folder organization';
