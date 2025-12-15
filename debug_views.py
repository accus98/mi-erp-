from core.db import Database
conn = Database.connect()
cr = conn.cursor()
cr.execute("SELECT id, name, model, length(arch) FROM ir_ui_view WHERE model='sale.order'")
rows = cr.fetchall()
print("ID | Name | Model | Arch Length")
for r in rows:
    print(f"{r[0]} | {r[1]} | {r[2]} | {r[3]}")
conn.close()
