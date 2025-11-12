-- Michaelhouse Leave System Database Schema
-- PostgreSQL 12+

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ==================== CORE TABLES ====================

-- Parents Table
CREATE TABLE parents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    parent_id VARCHAR(50) UNIQUE NOT NULL,  -- Authentication ID
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    email VARCHAR(255),
    phone VARCHAR(20),
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_parents_email ON parents(email);
CREATE INDEX idx_parents_phone ON parents(phone);
CREATE INDEX idx_parents_parent_id ON parents(parent_id);

-- Students Table
CREATE TABLE students (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    admin_number VARCHAR(10) UNIQUE NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    house VARCHAR(50) NOT NULL,  -- Finningley, Shepstone, etc.
    block CHAR(1) NOT NULL CHECK (block IN ('A', 'B', 'C', 'D', 'E')),
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_students_admin_number ON students(admin_number);
CREATE INDEX idx_students_house ON students(house);
CREATE INDEX idx_students_block ON students(block);

-- Student-Parent Linkage
CREATE TABLE student_parents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    parent_id UUID NOT NULL REFERENCES parents(id) ON DELETE CASCADE,
    primary_contact BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, parent_id)
);

CREATE INDEX idx_student_parents_student ON student_parents(student_id);
CREATE INDEX idx_student_parents_parent ON student_parents(parent_id);

-- Housemasters Table
CREATE TABLE housemasters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    hm_id VARCHAR(50) UNIQUE NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    house VARCHAR(50) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(20),
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_housemasters_email ON housemasters(email);
CREATE INDEX idx_housemasters_phone ON housemasters(phone);
CREATE INDEX idx_housemasters_house ON housemasters(house);

-- ==================== LEAVE MANAGEMENT ====================

-- Leave Balances (Per Term)
CREATE TABLE leave_balances (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    term_number INTEGER NOT NULL CHECK (term_number BETWEEN 1 AND 4),
    year INTEGER NOT NULL,
    overnight_total INTEGER DEFAULT 3,
    overnight_remaining INTEGER DEFAULT 3,
    friday_supper_total INTEGER DEFAULT 3,
    friday_supper_remaining INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, term_number, year)
);

CREATE INDEX idx_leave_balances_student ON leave_balances(student_id);
CREATE INDEX idx_leave_balances_term ON leave_balances(term_number, year);

-- Leave Register
CREATE TABLE leave_register (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    leave_id VARCHAR(50) UNIQUE NOT NULL,
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    student_admin_number VARCHAR(10) NOT NULL,
    student_first_name VARCHAR(100) NOT NULL,
    student_last_name VARCHAR(100) NOT NULL,
    student_house VARCHAR(50) NOT NULL,
    student_block CHAR(1) NOT NULL,
    leave_type VARCHAR(50) NOT NULL,  -- 'Overnight', 'Friday Supper', 'Day Leave', 'Special'
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    requesting_parent_id UUID REFERENCES parents(id),
    requesting_parent_name VARCHAR(200),
    approved_date TIMESTAMP,
    departure_timestamp TIMESTAMP,
    driver_id_capture TEXT,  -- NFR4.1: Driver ID data/image path
    status VARCHAR(50) DEFAULT 'Approved',  -- 'Approved', 'Cancelled'
    cancelled_by_hm_id UUID REFERENCES housemasters(id),
    cancellation_reason TEXT,
    cancelled_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_leave_register_student ON leave_register(student_id);
CREATE INDEX idx_leave_register_admin ON leave_register(student_admin_number);
CREATE INDEX idx_leave_register_dates ON leave_register(start_date, end_date);
CREATE INDEX idx_leave_register_status ON leave_register(status);
CREATE INDEX idx_leave_register_departure ON leave_register(departure_timestamp);

-- Leave Restrictions
CREATE TABLE leave_restrictions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    student_admin_number VARCHAR(10) NOT NULL,
    hm_id UUID NOT NULL REFERENCES housemasters(id),
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    reason TEXT NOT NULL,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_leave_restrictions_student ON leave_restrictions(student_id);
CREATE INDEX idx_leave_restrictions_dates ON leave_restrictions(start_date, end_date);
CREATE INDEX idx_leave_restrictions_active ON leave_restrictions(active);

-- ==================== CONFIGURATION ====================

-- Term Configuration
CREATE TABLE term_config (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    year INTEGER NOT NULL,
    term_number INTEGER NOT NULL CHECK (term_number BETWEEN 1 AND 4),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    half_term_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(year, term_number)
);

CREATE INDEX idx_term_config_year ON term_config(year);

-- Closed Weekends Configuration
CREATE TABLE closed_weekends (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    term_id UUID NOT NULL REFERENCES term_config(id) ON DELETE CASCADE,
    block CHAR(1) NOT NULL CHECK (block IN ('D', 'E')),  -- Only D and E blocks
    weekend_date DATE NOT NULL,
    reason VARCHAR(200) NOT NULL,  -- 'First weekend of term', 'Weekend after half term'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(term_id, block, weekend_date)
);

CREATE INDEX idx_closed_weekends_term ON closed_weekends(term_id);
CREATE INDEX idx_closed_weekends_date ON closed_weekends(weekend_date);

-- ==================== AUDIT & LOGGING ====================

-- Request Log (for monitoring)
CREATE TABLE request_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    channel VARCHAR(50) NOT NULL,  -- 'whatsapp', 'email'
    sender_identifier VARCHAR(255) NOT NULL,
    request_type VARCHAR(50) NOT NULL,  -- 'parent_leave', 'hm_query', 'hm_cancel', etc.
    message_text TEXT,
    result_status VARCHAR(50),
    result_message TEXT,
    processing_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_request_log_channel ON request_log(channel);
CREATE INDEX idx_request_log_created ON request_log(created_at);
CREATE INDEX idx_request_log_status ON request_log(result_status);

-- ==================== TRIGGERS ====================

-- Update updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_parents_updated_at BEFORE UPDATE ON parents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_students_updated_at BEFORE UPDATE ON students
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_housemasters_updated_at BEFORE UPDATE ON housemasters
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_leave_balances_updated_at BEFORE UPDATE ON leave_balances
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_leave_register_updated_at BEFORE UPDATE ON leave_register
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_leave_restrictions_updated_at BEFORE UPDATE ON leave_restrictions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_term_config_updated_at BEFORE UPDATE ON term_config
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ==================== VIEWS ====================

-- Active Leave View (for Guard app)
CREATE VIEW active_leaves AS
SELECT
    lr.leave_id,
    lr.student_admin_number,
    lr.student_first_name,
    lr.student_last_name,
    lr.student_house,
    lr.leave_type,
    lr.start_date,
    lr.end_date,
    lr.requesting_parent_name,
    lr.departure_timestamp,
    lr.status
FROM leave_register lr
WHERE lr.status = 'Approved'
  AND lr.departure_timestamp IS NULL
  AND lr.start_date <= CURRENT_TIMESTAMP
  AND lr.end_date >= CURRENT_TIMESTAMP;

-- Student Leave Summary
CREATE VIEW student_leave_summary AS
SELECT
    s.admin_number,
    s.first_name,
    s.last_name,
    s.house,
    s.block,
    lb.overnight_remaining,
    lb.friday_supper_remaining,
    COUNT(CASE WHEN lr.status = 'Approved' THEN 1 END) as approved_leaves_count,
    COUNT(CASE WHEN lr.status = 'Cancelled' THEN 1 END) as cancelled_leaves_count
FROM students s
LEFT JOIN leave_balances lb ON s.id = lb.student_id
LEFT JOIN leave_register lr ON s.id = lr.student_id
WHERE s.active = true
  AND (lb.year IS NULL OR lb.year = EXTRACT(YEAR FROM CURRENT_DATE))
  AND (lb.term_number IS NULL OR lb.term_number =
       (SELECT term_number FROM term_config
        WHERE CURRENT_DATE BETWEEN start_date AND end_date
        LIMIT 1))
GROUP BY s.id, s.admin_number, s.first_name, s.last_name, s.house, s.block,
         lb.overnight_remaining, lb.friday_supper_remaining;

-- ==================== COMMENTS ====================

COMMENT ON TABLE parents IS 'Parent/Guardian information for authentication and linkage';
COMMENT ON TABLE students IS 'Student records with house and block (grade) information';
COMMENT ON TABLE student_parents IS 'Many-to-many relationship between students and parents';
COMMENT ON TABLE housemasters IS 'Housemaster information for special leave approval';
COMMENT ON TABLE leave_balances IS 'Per-term leave balances (3 overnight + 3 Friday supper per term)';
COMMENT ON TABLE leave_register IS 'Complete leave approval register with departure tracking';
COMMENT ON TABLE leave_restrictions IS 'Housemaster-imposed leave restrictions by date range';
COMMENT ON TABLE term_config IS 'Academic term dates configuration (4 terms per year)';
COMMENT ON TABLE closed_weekends IS 'Blocked weekends for E and D blocks';
COMMENT ON TABLE request_log IS 'Audit log of all leave requests and responses';
