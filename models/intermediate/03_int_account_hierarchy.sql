DROP TABLE IF EXISTS int_account_hierarchy;
CREATE TABLE int_account_hierarchy AS
WITH RECURSIVE tree(account_id, root_account_id, hierarchy_depth, hierarchy_path) AS (
    SELECT account_id, account_id, 0, account_id
    FROM stg_accounts
    WHERE parent_account_id IS NULL
    UNION ALL
    SELECT c.account_id, t.root_account_id, t.hierarchy_depth + 1,
           t.hierarchy_path || ' > ' || c.account_id
    FROM stg_accounts c
    JOIN tree t ON c.parent_account_id = t.account_id
    WHERE instr(t.hierarchy_path, c.account_id) = 0
)
SELECT * FROM tree;
