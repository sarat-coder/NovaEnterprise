-- NovaEnterprise — seed data (Postgres dialect)
-- For SQLite + local development the seed_service.py loads sample_data/*.json directly.
-- This file is the Postgres equivalent; apply after schema.sql.

-- Teams
INSERT INTO teams (id, name, slug, description, lead_email) VALUES
  (1, 'Payments Platform', 'payments-platform', 'Owns all payment processing infrastructure', 'alice.chen@novaenterprise.internal'),
  (2, 'Identity',          'identity',          'Owns authentication and authorisation',       'bob.sharma@novaenterprise.internal'),
  (3, 'Data Platform',     'data-platform',     'Owns ETL pipelines and analytics warehouse',  'carol.nguyen@novaenterprise.internal'),
  (4, 'Customer Success',  'customer-success',  'Owns Customer Portal and Notification Service','david.okonkwo@novaenterprise.internal'),
  (5, 'SRE',               'sre',               'Site Reliability Engineering',                'eva.kowalski@novaenterprise.internal'),
  (6, 'Analytics',         'analytics',         'Business intelligence and reporting',          'frank.ibrahim@novaenterprise.internal')
ON CONFLICT (id) DO NOTHING;

-- Services
INSERT INTO services (id, name, slug, owner_team_id, tier) VALUES
  (1, 'Payments API',         'payments-api',         1, 'tier-1'),
  (2, 'Identity Service',     'identity-service',     2, 'tier-1'),
  (3, 'Data Pipeline',        'data-pipeline',        3, 'tier-2'),
  (4, 'Analytics Dashboard',  'analytics-dashboard',  6, 'tier-2'),
  (5, 'Notification Service', 'notification-service', 4, 'tier-2'),
  (6, 'Billing Engine',       'billing-engine',       1, 'tier-1'),
  (7, 'Customer Portal',      'customer-portal',      4, 'tier-2'),
  (8, 'Search Service',       'search-service',       5, 'tier-2')
ON CONFLICT (id) DO NOTHING;

-- Customers (abbreviated — full set in sample_data/customers.json)
INSERT INTO customers (id, name, slug, segment, industry, contract_tier) VALUES
  (1,  'Meridian Financial Group', 'meridian-financial',  'enterprise',  'Financial Services', 'platinum'),
  (2,  'Apex Retail Corp',         'apex-retail',         'enterprise',  'Retail',             'gold'),
  (3,  'NovaTech Solutions',       'novatech-solutions',  'enterprise',  'Technology',         'platinum'),
  (4,  'Sunrise Healthcare',       'sunrise-healthcare',  'mid-market',  'Healthcare',         'silver'),
  (5,  'Coastal Logistics',        'coastal-logistics',   'mid-market',  'Logistics',          'silver'),
  (6,  'GreenLeaf Education',      'greenleaf-education', 'mid-market',  'Education',          'silver'),
  (7,  'Pinnacle Media',           'pinnacle-media',      'mid-market',  'Media',              'bronze'),
  (8,  'Swift Deliveries',         'swift-deliveries',    'smb',         'Logistics',          'starter'),
  (9,  'BlueSky Analytics',        'bluesky-analytics',   'smb',         'Technology',         'starter'),
  (10, 'Harbor Hospitality',       'harbor-hospitality',  'smb',         'Hospitality',        'starter')
ON CONFLICT (id) DO NOTHING;
