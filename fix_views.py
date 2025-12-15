from core.db import Database
conn = Database.connect()
cr = conn.cursor()
# Delete bad views
cr.execute("DELETE FROM ir_ui_view WHERE id < 17 AND model='sale.order'")
print(f"Deleted {cr.rowcount} bad views.")
# Also clean up their IMD entries if any?
# Leave them, harmless.
conn.commit()
conn.close()
