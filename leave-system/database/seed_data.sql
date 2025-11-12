-- Seed Data for Michaelhouse Leave System
-- Test data for development and demonstration

-- ==================== HOUSEMASTERS ====================

INSERT INTO housemasters (hm_id, first_name, last_name, house, email, phone) VALUES
('HM_001', 'John', 'Finningley', 'Finningley', 'hm.finningley@michaelhouse.org', '27831112222'),
('HM_002', 'Peter', 'Shepstone', 'Shepstone', 'hm.shepstone@michaelhouse.org', '27831113333'),
('HM_003', 'David', 'Transvaal', 'Transvaal', 'hm.transvaal@michaelhouse.org', '27831114444'),
('HM_004', 'Michael', 'Tatham', 'Tatham', 'hm.tatham@michaelhouse.org', '27831115555');

-- ==================== PARENTS ====================

INSERT INTO parents (parent_id, first_name, last_name, email, phone) VALUES
('PARENT_001', 'John', 'Smith', 'john.smith@example.com', '27603174174'),
('PARENT_002', 'Jane', 'Doe', 'jane.doe@example.com', '27821234567'),
('PARENT_003', 'Robert', 'Johnson', 'robert.johnson@example.com', '27831234567'),
('PARENT_004', 'Sarah', 'Williams', 'sarah.williams@example.com', '27841234567');

-- ==================== STUDENTS ====================

INSERT INTO students (admin_number, first_name, last_name, house, block) VALUES
('12345', 'James', 'Smith', 'Finningley', 'C'),
('67890', 'Michael', 'Doe', 'Shepstone', 'E'),
('11111', 'David', 'Johnson', 'Transvaal', 'D'),
('22222', 'Andrew', 'Williams', 'Tatham', 'B'),
('33333', 'Christopher', 'Brown', 'Finningley', 'E'),
('44444', 'Matthew', 'Jones', 'Shepstone', 'C');

-- ==================== STUDENT-PARENT LINKAGE ====================

INSERT INTO student_parents (student_id, parent_id, primary_contact)
SELECT s.id, p.id, true
FROM students s, parents p
WHERE s.admin_number = '12345' AND p.parent_id = 'PARENT_001';

INSERT INTO student_parents (student_id, parent_id, primary_contact)
SELECT s.id, p.id, true
FROM students s, parents p
WHERE s.admin_number = '67890' AND p.parent_id = 'PARENT_002';

INSERT INTO student_parents (student_id, parent_id, primary_contact)
SELECT s.id, p.id, true
FROM students s, parents p
WHERE s.admin_number = '11111' AND p.parent_id = 'PARENT_003';

INSERT INTO student_parents (student_id, parent_id, primary_contact)
SELECT s.id, p.id, true
FROM students s, parents p
WHERE s.admin_number = '22222' AND p.parent_id = 'PARENT_004';

-- ==================== TERM CONFIGURATION ====================

-- 2025 Academic Year
INSERT INTO term_config (year, term_number, start_date, end_date, half_term_date) VALUES
(2025, 1, '2025-01-15', '2025-03-28', '2025-02-15'),
(2025, 2, '2025-04-22', '2025-06-27', '2025-05-24'),
(2025, 3, '2025-07-22', '2025-09-26', '2025-08-23'),
(2025, 4, '2025-10-07', '2025-12-05', '2025-11-08');

-- ==================== CLOSED WEEKENDS ====================

-- Term 1 - 2025
INSERT INTO closed_weekends (term_id, block, weekend_date, reason)
SELECT id, 'E', '2025-01-18', 'First weekend of term'
FROM term_config WHERE year = 2025 AND term_number = 1;

INSERT INTO closed_weekends (term_id, block, weekend_date, reason)
SELECT id, 'D', '2025-01-18', 'First weekend of term'
FROM term_config WHERE year = 2025 AND term_number = 1;

INSERT INTO closed_weekends (term_id, block, weekend_date, reason)
SELECT id, 'E', '2025-02-22', 'Weekend after half term'
FROM term_config WHERE year = 2025 AND term_number = 1;

INSERT INTO closed_weekends (term_id, block, weekend_date, reason)
SELECT id, 'D', '2025-02-22', 'Weekend after half term'
FROM term_config WHERE year = 2025 AND term_number = 1;

-- Term 2 - 2025
INSERT INTO closed_weekends (term_id, block, weekend_date, reason)
SELECT id, 'E', '2025-04-26', 'First weekend of term'
FROM term_config WHERE year = 2025 AND term_number = 2;

INSERT INTO closed_weekends (term_id, block, weekend_date, reason)
SELECT id, 'D', '2025-04-26', 'First weekend of term'
FROM term_config WHERE year = 2025 AND term_number = 2;

INSERT INTO closed_weekends (term_id, block, weekend_date, reason)
SELECT id, 'E', '2025-05-31', 'Weekend after half term'
FROM term_config WHERE year = 2025 AND term_number = 2;

INSERT INTO closed_weekends (term_id, block, weekend_date, reason)
SELECT id, 'D', '2025-05-31', 'Weekend after half term'
FROM term_config WHERE year = 2025 AND term_number = 2;

-- ==================== LEAVE BALANCES ====================

-- Initialize balances for Term 1, 2025 for all students
INSERT INTO leave_balances (student_id, term_number, year, overnight_total, overnight_remaining, friday_supper_total, friday_supper_remaining)
SELECT s.id, 1, 2025, 3, 3, 3, 3
FROM students s;

-- Student 67890 (Michael Doe) has used one overnight leave
UPDATE leave_balances lb
SET overnight_remaining = 2
FROM students s
WHERE lb.student_id = s.id AND s.admin_number = '67890' AND lb.term_number = 1 AND lb.year = 2025;

-- ==================== SAMPLE LEAVE REGISTER ENTRIES ====================

-- Approved overnight leave for James Smith
INSERT INTO leave_register (
    leave_id, student_id, student_admin_number, student_first_name, student_last_name,
    student_house, student_block, leave_type, start_date, end_date,
    requesting_parent_id, requesting_parent_name, approved_date, status
)
SELECT
    'LEAVE_001',
    s.id,
    s.admin_number,
    s.first_name,
    s.last_name,
    s.house,
    s.block,
    'Overnight',
    '2025-02-08 14:00:00',
    '2025-02-09 18:50:00',
    p.id,
    p.first_name || ' ' || p.last_name,
    CURRENT_TIMESTAMP,
    'Approved'
FROM students s, parents p
WHERE s.admin_number = '12345' AND p.parent_id = 'PARENT_001';

-- Active leave for testing Guard app
INSERT INTO leave_register (
    leave_id, student_id, student_admin_number, student_first_name, student_last_name,
    student_house, student_block, leave_type, start_date, end_date,
    requesting_parent_id, requesting_parent_name, approved_date, status
)
SELECT
    'LEAVE_002',
    s.id,
    s.admin_number,
    s.first_name,
    s.last_name,
    s.house,
    s.block,
    'Day Leave',
    CURRENT_TIMESTAMP - INTERVAL '1 hour',
    CURRENT_TIMESTAMP + INTERVAL '4 hours',
    p.id,
    p.first_name || ' ' || p.last_name,
    CURRENT_TIMESTAMP - INTERVAL '2 hours',
    'Approved'
FROM students s, parents p
WHERE s.admin_number = '67890' AND p.parent_id = 'PARENT_002';

-- ==================== SAMPLE RESTRICTION ====================

-- Student 11111 (David Johnson) is restricted for February
INSERT INTO leave_restrictions (student_id, student_admin_number, hm_id, start_date, end_date, reason, active)
SELECT
    s.id,
    s.admin_number,
    h.id,
    '2025-02-01 00:00:00',
    '2025-02-28 23:59:59',
    'Academic concerns - must focus on studies',
    true
FROM students s, housemasters h
WHERE s.admin_number = '11111' AND h.hm_id = 'HM_003';

-- ==================== VERIFICATION QUERIES ====================

-- Verify all data loaded correctly
DO $$
BEGIN
    RAISE NOTICE 'Data seeded successfully:';
    RAISE NOTICE '  Parents: %', (SELECT COUNT(*) FROM parents);
    RAISE NOTICE '  Students: %', (SELECT COUNT(*) FROM students);
    RAISE NOTICE '  Housemasters: %', (SELECT COUNT(*) FROM housemasters);
    RAISE NOTICE '  Student-Parent Links: %', (SELECT COUNT(*) FROM student_parents);
    RAISE NOTICE '  Term Configs: %', (SELECT COUNT(*) FROM term_config);
    RAISE NOTICE '  Closed Weekends: %', (SELECT COUNT(*) FROM closed_weekends);
    RAISE NOTICE '  Leave Balances: %', (SELECT COUNT(*) FROM leave_balances);
    RAISE NOTICE '  Leave Register: %', (SELECT COUNT(*) FROM leave_register);
    RAISE NOTICE '  Restrictions: %', (SELECT COUNT(*) FROM leave_restrictions);
END $$;
