-- SQL script to create contacts table in Supabase
-- ตารางสำหรับเก็บข้อมูลเบอร์โทร

CREATE TABLE IF NOT EXISTS contacts (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    name TEXT NOT NULL,
    phone_number TEXT NOT NULL,
    created_by TEXT NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index for better search performance
CREATE INDEX IF NOT EXISTS idx_contacts_name ON contacts USING gin(name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_contacts_phone ON contacts USING gin(phone_number gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_contacts_created_by ON contacts(created_by);
CREATE INDEX IF NOT EXISTS idx_contacts_created_at ON contacts(created_at);

-- Enable trigram extension for better partial text search
-- Run this first: CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Comments for each column
COMMENT ON TABLE contacts IS 'ตารางเก็บข้อมูลเบอร์โทรและชื่อผู้ติดต่อ';
COMMENT ON COLUMN contacts.id IS 'รหัสอัตโนมัติ';
COMMENT ON COLUMN contacts.created_at IS 'เวลาที่บันทึก';
COMMENT ON COLUMN contacts.name IS 'ชื่อเต็มหรือบางส่วน';
COMMENT ON COLUMN contacts.phone_number IS 'เบอร์โทร';
COMMENT ON COLUMN contacts.created_by IS 'LINE User ID ที่เพิ่มข้อมูล';
COMMENT ON COLUMN contacts.updated_at IS 'เวลาที่แก้ไขล่าสุด';

-- Sample data (optional)
-- INSERT INTO contacts (name, phone_number, created_by) VALUES 
-- ('สมชาย', '081-234-5678', 'sample_user_id'),
-- ('สมหญิง', '089-999-8888', 'sample_user_id');