-- ============================================================
-- HR & IT Helpdesk Database Seed
-- ============================================================

-- Drop existing tables (safe re-seed)
DROP TABLE IF EXISTS it_assets CASCADE;
DROP TABLE IF EXISTS employees CASCADE;

-- ---- Employees ----
CREATE TABLE employees (
    employee_id     VARCHAR(10)  PRIMARY KEY,
    full_name       VARCHAR(100) NOT NULL,
    email           VARCHAR(150) NOT NULL UNIQUE,
    phone           VARCHAR(20)  NOT NULL,
    ssn_last4       CHAR(4)      NOT NULL,
    department      VARCHAR(80)  NOT NULL,
    role            VARCHAR(80)  NOT NULL,
    annual_leave_balance INT NOT NULL DEFAULT 20,
    sick_leave_balance   INT NOT NULL DEFAULT 8,
    manager_id      VARCHAR(10)  REFERENCES employees(employee_id)
);

-- ---- IT Assets ----
CREATE TABLE it_assets (
    asset_id        VARCHAR(15)  PRIMARY KEY,
    employee_id     VARCHAR(10)  REFERENCES employees(employee_id),
    device_type     VARCHAR(50)  NOT NULL,
    serial_number   VARCHAR(50)  NOT NULL UNIQUE,
    assigned_date   DATE         NOT NULL,
    status          VARCHAR(30)  NOT NULL DEFAULT 'Active'
);

-- ============================================================
-- Seed Employees
-- ============================================================

-- E101 — Director (no manager)
INSERT INTO employees
    (employee_id, full_name, email, phone, ssn_last4, department, role, annual_leave_balance, sick_leave_balance, manager_id)
VALUES
    ('E101', 'Arjun Sharma',  'arjun.sharma@corp.internal',  '+1-408-555-0101', '7823', 'Engineering', 'Engineering Director', 18, 6, NULL);

-- E102 — Priya Nair (key test subject: 9 annual, 5 sick)
INSERT INTO employees
    (employee_id, full_name, email, phone, ssn_last4, department, role, annual_leave_balance, sick_leave_balance, manager_id)
VALUES
    ('E102', 'Priya Nair',    'priya.nair@corp.internal',    '+1-408-555-0102', '4491', 'Engineering', 'Senior Software Engineer', 9, 5, 'E101');

-- E103 — HR Manager
INSERT INTO employees
    (employee_id, full_name, email, phone, ssn_last4, department, role, annual_leave_balance, sick_leave_balance, manager_id)
VALUES
    ('E103', 'Marcus Webb',   'marcus.webb@corp.internal',   '+1-408-555-0103', '3317', 'Human Resources', 'HR Manager', 20, 8, 'E101');

-- E104 — IT Support Analyst
INSERT INTO employees
    (employee_id, full_name, email, phone, ssn_last4, department, role, annual_leave_balance, sick_leave_balance, manager_id)
VALUES
    ('E104', 'Chen Lin',      'chen.lin@corp.internal',      '+1-408-555-0104', '9952', 'IT', 'IT Support Analyst', 15, 3, 'E103');

-- ============================================================
-- Seed IT Assets
-- ============================================================

INSERT INTO it_assets
    (asset_id, employee_id, device_type, serial_number, assigned_date, status)
VALUES
    ('AST-901', 'E102', 'Laptop',   'SN-MBP-2023-XR991', '2023-04-10', 'Active'),
    ('AST-902', 'E101', 'Laptop',   'SN-DEL-2022-TH442', '2022-11-01', 'Active'),
    ('AST-903', 'E104', 'Docking Station', 'SN-DST-2024-BK001', '2024-01-15', 'Active');
