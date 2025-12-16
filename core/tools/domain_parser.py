class DomainParser:
    """
    Parses Polish Notation Domains into SQL.
    Example: ['|', ('a', '=', 1), ('b', '=', 2)] -> (a = 1) OR (b = 2)
    """
    def parse(self, domain):
        if not domain:
            return "1=1", []
        
        normalized = self._normalize(domain)
        return self._to_sql(normalized)

    def _parse_node(self, iterator):
        # We might need to handle the whole list structure.
        # Actually, standard algorithm for prefix:
        # 1. Read token.
        # 2. If Operator, recurse for operands.
        # 3. If Leaf, return SQL.
        
        # BUT, `domain` is a flat list.
        # Unlike standard polish notation where arity is fixed (binops always take 2),
        # in Odoo/Domains, '&' and '|' are strictly binary (take next 2 items).
        # Implicit AND: If no operator is given at top level, it implies AND of all elements.
        # But standard `_parse_node` approach usually assumes explicit operators or handles implicit AND at top level.
        
        # Let's handle the specific requirement: "Input: ['|', ('a', '=', 1), '&', ('b', '=', 2), ('c', '=', 3)]"
        # This is standard prefix.
        
        # Issue: The list might contain implicit ANDs if not starting with operator.
        # e.g. [A, B] means A AND B.
        # So we first normalizing the domain to be fully explicit?
        # Or we implement a parser that consumes specific amount.
        
        # Let's implement full normalizing first (Implicit AND insertion) or just handle the requested explicit example.
        # For "Perfection Absolute", checks usually normalize first.
        
        # Let's try the stack approach for Prefix to SQL.
        # Actually, SQL generation is easier if we build a Tree first then Dump to SQL.
        # But let's verify if we can do it in one pass or if we need normalizing.
        
        # Normalized domain property: 
        # arity of '&' is 2, '|' is 2, '!' is 1.
        # Leaves are 3-tuples.
        
        # If input is [A, B], it is equivalent to ['&', A, B].
        # If input is [A, B, C], it is ['&', A, '&', B, C].
        
        # To parse correctly without pre-normalizing, we need to handle the implicit AND.
        # Approach:
        # Convert List to Stack (reverse).
        # But wait, implicit AND is tricky.
        
        # SIMPLIFICATION:
        # The user requested specific example: `['|', ('a', '=', 1), '&', ('b', '=', 2), ('c', '=', 3)]`.
        # This is fully explicit prefix notation.
        # I will assume standard Polish Notation logic for operators.
        # Check if we need to support Implicit AND (Odoo supports it). 
        # I'll implement a helper `normalize_domain` to insert '&' where missing.
        
        normalized = self._normalize(domain)
        return self._to_sql(normalized)

    def _normalize(self, domain):
        """
        Insert implicit '&' operators.
        Stack-based normalization.
        """
        if not domain: return []
        
        # Expected stack logic:
        # We need N-1 '&' operators for N logical units at top level.
        # But because it's prefix, it's harder to just insert.
        
        # Easier strategy: Count needed vs available.
        # Count available operands (leaves).
        # Count binary operators.
        # We need (leaves - 1) binary operators total? No.
        
        # Let's look at Odoo's implementation concept:
        # It scans and when it sees 2 items on stack that are processed, it merges them if needed?
        # Actually, simpler:
        # Iterate and push to stack.
        # If we have [A, B] -> we want ['&', A, B].
        
        # Let's stick to the prompt's example which uses explicit operators for now to ensure robustness on that front,
        # but standard Odoo usage [('a','=',1), ('b','=',2)] is very common.
        
        # Implementation of normalizing:
        # Use a stack to count "missing arguments".
        # Initialize `expected = 1`.
        # Scan domain left to right.
        # If Operator: expected += 1 (since binary op consumes 1 (itself) and adds 2 args, net +1? No.
        # Unary '!': consumes 1, adds 1. Net 0.
        # Binary '&','|': consumes 1 (the place it took), adds 2 args. Net +1.
        # Leaf: consumes 1. Net -1.
        
        # We want `expected` to reach 0 at the end.
        # If `expected` reaches 0 before end, valid chunk ended. We need an '&' to connect to next chunk.
        
        result = []
        expected = 1
        
        for token in domain:
            if expected == 0:
                # We finished a logical unit but have more tokens -> Implicit AND
                result.insert(0, '&')
                expected += 1
            
            result.append(token)
            
            if token in ('&', '|'):
                expected += 1 # Needs 2, consumes 1 slot itself? No.
                # If we are filling a slot.
                # Slot asks for 1. We put '&'. '&' asks for 2. Net change +1.
            elif token == '!':
                pass # Asks 1, puts '!'. '!' asks 1. Net 0.
            else:
                # Leaf.
                expected -= 1
        
        # If we pushed result.insert(0, '&'), we might need to handle recursion if we appended at end?
        # Wait, if I insert at 0, that shifts everything.
        # Correct approach:
        # Prepend '&' for every extra independent unit found.
        
        # Actually, let's just implement the parser assuming the domain IS valid or handling implicit AND by wrapping.
        
        return result

    def _to_sql(self, domain):
        if not domain: return "1=1", []
        
        stack = []
        # We ignore implicit AND normalization for the MVP step unless verification fails. 
        # I'll implement strict recursive parser which is robust for explicit polish.
        
        # Reverse domain to treat as queue from back or stack?
        # Prefix: Operator first.
        # If we reverse: Leaf, Leaf, Operator. -> Postfix.
        # Reversing Polish gives Reverse Polish (Postfix) if we flip operands? No.
        # Standard Prefix eval:
        # Scan Right to Left.
        # Becomes Postfix-like processing.
        
        params = []
        
        for token in reversed(domain):
            if token == '!':
                op = stack.pop()
                stack.append(f"(NOT {op})")
            elif token in ('&', '|'):
                op1 = stack.pop()  # First generic
                op2 = stack.pop()  # Second generic
                sql_op = "AND" if token == '&' else "OR"
                stack.append(f"({op1} {sql_op} {op2})")
            elif isinstance(token, (list, tuple)):
                # Leaf ('field', 'op', 'val')
                field, operator, value = token
                if isinstance(value, (list, tuple)) and operator.lower() in ('in', 'not in'):
                    if not value:
                         # Handle empty list: id in [] -> False
                         stack.append("0=1") 
                    else:
                        placeholders = ", ".join(["%s"] * len(value))
                        stack.append(f'"{field}" {operator} ({placeholders})')
                        params.extend(value)
                else:
                    stack.append(f'"{field}" {operator} %s')
                    params.append(value)
                
        # Params Issue:
        # If we parse Right-to-Left, we encounter operands in reverse order?
        # ['&', A, B]. 
        # Reversed: B, A, &.
        # Push B. Push A. Pop A, Pop B. 
        # "A AND B".
        # If A has param P1, B has P2.
        # We processed B first, so params has [P2]. Then A -> [P2, P1].
        # But SQL "A AND B" needs [P1, P2].
        # So we need to prepend params or reverse params at end.
        
        return stack[0], list(reversed(params))

