from core.orm import Model
from core.tools.sql import SQLParams
from core.tools.domain_parser import DomainParser

# @pytest.mark.asyncio -> Not needed for main run
async def test_native_sql_generation():
    """
    Verify that DomainParser + SQLParams generates $n placeholders
    without string replacement.
    """
    sql = SQLParams()
    parser = DomainParser()
    
    # Complex Domain
    domain = ['|', ('name', '=', 'Test'), '&', ('age', '>', 10), ('active', '=', True)]
    
    # Parse with builder
    clause, _ = parser.parse(domain, param_builder=sql)
    
    print(f"Generated Clause: {clause}")
    print(f"Params: {sql.get_params()}")
    
    # Assertions
    assert '$1' in clause
    assert '$2' in clause
    assert '$3' in clause
    assert '%s' not in clause
    
    # Verify params order
    # Polish: OR(name=Test, AND(age>10, active=True))
    # Reversed parse: active, age, &, name, |
    # 1. active=True -> $1
    # 2. age>10 -> $2
    # 3. AND ($2, $1) -> (age>10 AND active=True)
    # 4. name=Test -> $3
    # 5. OR ($3, AND...) -> (name=Test OR (...))
    
    assert sql.get_params() == (True, 10, 'Test') 
    # Valid? Polish traversal logic:
    # Stack push order: | (pop 2), name, & (pop 2), age, active.
    # Wait, Parser scans REVERSED domain?
    # domain =['|', A, '&', B, C]
    # Reversed: [C, B, &, A, |]
    # 1. C (active). Pushed to params ($1). Stack: ["active=$1"]
    # 2. B (age). Pushed to params ($2). Stack: ["active=$1", "age=$2"]
    # 3. &. Pop B, C. Push (B AND C). Stack: ["(age=$2 AND active=$1)"]
    # 4. A (name). Pushed to params ($3). Stack: ["(...)", "name=$3"]
    # 5. |. Pop A, (...). Push (A OR ...).
    
    # So Params should be: [True, 10, 'Test'] -> $1=True, $2=10, $3=Test.
    # Clause: (name=$3 OR (age=$2 AND active=$1))
    
    assert clause == '("name" = $3 OR ("age" > $2 AND "active" = $1))'

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_native_sql_generation())
