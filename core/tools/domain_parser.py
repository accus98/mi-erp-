try:
    from pypika import Table, Field, Parameter
    from pypika.terms import Criterion, Term
except ImportError:
    Table, Field, Parameter, Criterion, Term = None, None, None, None, None

class DomainParser:
    """
    Parses Polish Notation Domains into SQL.
    Now supports Pypika for safe Query Building.
    """
    def parse_pypika(self, domain, table, param_builder):
        """
        Parse domain to Pypika Criterion.
        :param domain: List of polish notation tuples.
        :param table: Pypika Table object.
        :param param_builder: SQLParams instance.
        :return: Pypika Criterion (or None if empty)
        """
        if not domain:
            return None
            
        normalized = self._normalize(domain)
        return self._to_pypika(normalized, table, param_builder)

    def _to_pypika(self, domain, table, param_builder):
        if not domain: return None
        
        stack = []
        
        for token in reversed(domain):
            if token == '!':
                op = stack.pop()
                stack.append(op.negate()) # Pypika criterion negation? usually ~op or op.negate()
            elif token == '&':
                op1 = stack.pop()
                op2 = stack.pop()
                stack.append(op1 & op2)
            elif token == '|':
                op1 = stack.pop()
                op2 = stack.pop()
                stack.append(op1 | op2)
            elif isinstance(token, (list, tuple)):
                # Leaf
                field_name, operator, value = token
                field = table[field_name]
                
                # Special Cases
                if (value is False or value is None) and operator in ('=', '!='):
                    if operator == '=':
                        stack.append(field.isnull())
                    elif operator == '!=':
                        stack.append(field.notnull())
                    else:
                        # Fallback for wacky calls
                         ph = param_builder.add(value)
                         # We can't express custom op easily in simple pypika field api
                         # Use criterion from string? No.
                         # Assume '=' behavior?
                         stack.append(field == Parameter(ph))

                elif isinstance(value, (list, tuple)) and operator.lower() in ('in', 'not in'):
                    if not value:
                         # Empty list IN -> False.
                         # Pypika doesn't have explicit False criterion?
                         # Use 1=0
                         from pypika.terms import BasicCriterion, CustomFunction
                         # stack.append(BasicCriterion(CustomFunction('1', []), CustomFunction('0', []), '=')) 
                         # Simpler: table.id.ne(table.id) ? 
                         stack.append(field != field) 
                    else:
                         placeholders = []
                         for v in value:
                             placeholders.append(Parameter(param_builder.add(v)))
                         
                         if operator.lower() == 'in':
                             stack.append(field.isin(placeholders))
                         else:
                             stack.append(field.notin(placeholders))
                elif operator == 'ilike':
                     ph = param_builder.add(value)
                     stack.append(field.ilike(Parameter(ph)))
                elif operator == 'like':
                     ph = param_builder.add(value)
                     stack.append(field.like(Parameter(ph)))
                elif operator == '>':
                     ph = param_builder.add(value)
                     stack.append(field > Parameter(ph))
                elif operator == '<':
                     ph = param_builder.add(value)
                     stack.append(field < Parameter(ph))
                elif operator == '>=':
                     ph = param_builder.add(value)
                     stack.append(field >= Parameter(ph))
                elif operator == '<=':
                     ph = param_builder.add(value)
                     stack.append(field <= Parameter(ph))
                elif operator == '!=':
                     ph = param_builder.add(value)
                     stack.append(field != Parameter(ph))
                else:
                     # Default '='
                     ph = param_builder.add(value)
                     stack.append(field == Parameter(ph))
        
        if not stack:
             return None
        return stack[0]

    def parse(self, domain, param_builder=None):
        """
        Parse domain to SQL.
        :param domain: List of polish notation tuples.
        :param param_builder: Optional SQLParams instance. If provided, generates $n placeholders.
                             If None, generates %s and returns params list.
        :return: (sql_string, params_list)
        """
        if not domain:
            return "1=1", []
        
        normalized = self._normalize(domain)
        return self._to_sql(normalized, param_builder)

    def _normalize(self, domain):
        """
        Insert implicit '&' operators.
        """
        if not domain: return []
        
        result = []
        expected = 1
        
        for token in domain:
            if expected == 0:
                result.insert(0, '&')
                expected += 1
            
            result.append(token)
            
            if token in ('&', '|'):
                expected += 1
            elif token == '!':
                pass
            else:
                expected -= 1
        
        return result

    def _to_sql(self, domain, param_builder=None):
        if not domain: return "1=1", []
        
        stack = []
        params = []
        
        for token in reversed(domain):
            if token == '!':
                op = stack.pop()
                stack.append(f"(NOT {op})")
            elif token in ('&', '|'):
                op1 = stack.pop()
                op2 = stack.pop()
                sql_op = "AND" if token == '&' else "OR"
                stack.append(f"({op1} {sql_op} {op2})")
            elif isinstance(token, (list, tuple)):
                # Leaf ('field', 'op', 'val')
                field, operator, value = token
                
                # Check for False/None (IS NULL/IS NOT NULL)
                if (value is False or value is None) and operator in ('=', '!='):
                    if operator == '=':
                        stack.append(f'"{field}" IS NULL')
                    elif operator == '!=':
                        stack.append(f'"{field}" IS NOT NULL')
                    else:
                        # Should not happen usually
                        ph = "%s"
                        if param_builder:
                            ph = param_builder.add(value)
                        else:
                            params.append(value)
                        stack.append(f'"{field}" {operator} {ph}')
                        
                elif isinstance(value, (list, tuple)) and operator.lower() in ('in', 'not in'):
                    if not value:
                         # Handle empty list: id in [] -> False (0=1)
                         stack.append("0=1") 
                    else:
                        if param_builder:
                            ph_str = param_builder.add_many(value)
                            stack.append(f'"{field}" {operator} ({ph_str})')
                        else:
                            placeholders = ", ".join(["%s"] * len(value))
                            stack.append(f'"{field}" {operator} ({placeholders})')
                            params.extend(value)
                else:
                    if operator == '@@':
                        # Native Full-Text Search
                        # to_tsvector('spanish', field) @@ plainto_tsquery('spanish', value)
                        # We use 'spanish' hardcoded for now or use 'simple'?
                        # Ideally configured. Let's start with 'simple' for universality or 'spanish' as requested?
                        # User logic implies Spanish ERP.
                        config = 'spanish'
                        
                        if param_builder:
                            ph = param_builder.add(value)
                            stack.append(f"to_tsvector('{config}', \"{field}\") @@ plainto_tsquery('{config}', {ph})")
                        else:
                            stack.append(f"to_tsvector('{config}', \"{field}\") @@ plainto_tsquery('{config}', %s)")
                            params.append(value)
                    elif operator == 'search':
                        # Google-style Full-Text Search
                        config = 'spanish'
                        if param_builder:
                            ph = param_builder.add(value)
                            stack.append(f"to_tsvector('{config}', \"{field}\") @@ plainto_tsquery('{config}', {ph})")
                        else:
                            stack.append(f"to_tsvector('{config}', \"{field}\") @@ plainto_tsquery('{config}', %s)")
                            params.append(value)
                    else:
                        if param_builder:
                            ph = param_builder.add(value)
                            stack.append(f'"{field}" {operator} {ph}')
                        else:
                             stack.append(f'"{field}" {operator} %s')
                             params.append(value)
                
        # If param_builder was used, params list is empty (managed by builder)
        # If not, we must reverse the gathered params because we parsed Right-To-Left
        
        final_params = []
        if not param_builder:
            final_params = list(reversed(params))
            
        return stack[0], final_params

