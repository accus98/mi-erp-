import sqlparams

query = 'SELECT id FROM "res_users" WHERE "login" = %s'
args = ('admin',)

converter = sqlparams.SQLParams('numeric_dollar', 'format')
pg_query, new_args = converter.format(query, args)

print(f"Original: {query}")
print(f"Converted: {pg_query}")
print(f"Args: {new_args}")

# Check if escaping happens
query2 = 'SELECT id FROM "res_users" WHERE "login" = %%s'
pg_query2, new_args2 = converter.format(query2, args)
print(f"Original Ecscaped: {query2}")
print(f"Converted Escaped: {pg_query2}")
