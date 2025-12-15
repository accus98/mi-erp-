import sys
import os
from core.orm import Model
from core.fields import Integer, Char, Many2many
from core.db import Database
from core.env import Environment

# Models
class TestGroup(Model):
    _name = 'test.group'
    name = Char(string='Group Name')

class TestUser(Model):
    _name = 'test.user'
    name = Char(string='User Name')
    # M2M: Auto-named pivot: test_group_test_user_rel
    group_ids = Many2many('test.group', string='Groups')

def run_test():
    print("--- Testing Many2many ---")
    try:
        conn = Database.connect()
        cr = Database.cursor(conn)
        
        TestGroup._auto_init(cr)
        TestUser._auto_init(cr) # Should create pivot table
        
        env = Environment(cr, uid=1)
        User = env['test.user']
        Group = env['test.group']
        
        # 1. Create Groups
        g1 = Group.create({'name': 'Admin'})
        g2 = Group.create({'name': 'Sales'})
        print(f"Groups: {g1.ids}, {g2.ids}")
        
        # 2. Create User with M2M
        # Passing list of IDs
        u = User.create({
            'name': 'Bob',
            'group_ids': [g1.ids[0], g2.ids[0]]
        })
        print(f"Created User: {u.name}")
        
        # 3. Read Back
        # u.group_ids should be RecordSet
        print(f"User Groups: {u.group_ids}")
        names = [g.name for g in u.group_ids]
        print(f"Group Names: {names}")
        
        if 'Admin' in names and 'Sales' in names:
             print("SUCCESS: M2M Write/Read works.")
        else:
             print("FAILURE: M2M Read failed.")

        # 4. Update (Replace)
        u.write({'group_ids': [g1.ids[0]]}) # Remove Sales
        print("Updated Groups (Removed Sales)")
        
        # Verify
        # Need to re-read or rely on cache update?
        # Our M2M __get__ always queries DB currently (no cache for M2M yet in __get__).
        # See Many2many.__get__ in fields.py -> It SELECTs.
        
        new_names = [g.name for g in u.group_ids]
        print(f"New Group Names: {new_names}")
        
        if len(new_names) == 1 and 'Admin' in new_names:
            print("SUCCESS: M2M Update works.")
        else:
             print("FAILURE: M2M Update failed.")

        conn.commit()
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
