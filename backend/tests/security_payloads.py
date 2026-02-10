
# tests/security/payloads.py

class PayloadFactory:
    """
    Industrial-grade fuzzing payloads for API security testing.
    """
    
    SQL_INJECTION = [
        "' OR '1'='1",
        "admin' --",
        "admin' #",
        "' UNION SELECT 1, 'admin', 'password' --",
        "1; DROP TABLE users",
        "' OR 1=1; --",
        "admin'/*",
        "' OR '1'='1' --",
        "') OR ('1'='1",
        "'; EXEC xp_cmdshell('dir'); --",
        "1' AND 1=(SELECT COUNT(*) FROM tablename); --",
        "1' AND 1=0 UNION ALL SELECT 'admin', '81dc9bdb52d04dc20036dbd8313ed055' -- ",
        "1' OR '1'='1",
        "1' OR '1'='1' --",
        "1' OR '1'='1' ({",
        "1' OR '1'='1' /*"
    ]
    
    XSS_PAYLOADS = [
        "<script>alert(1)</script>",
        "\"><script>alert(1)</script>",
        "<img src=x onerror=alert(1)>",
        "javascript:alert(1)",
        "<svg/onload=alert(1)>",
        "<iframe src=javascript:alert(1)>",
        "<body onload=alert(1)>",
        "<a href=\"javascript:alert(1)\">Click me</a>",
        "<math><maction actiontype=statusline#http://google.com/ xlink:href=javascript:alert(1)>CLICKME</maction></math>",
        "<form><button formaction=javascript&colon;alert(1)>CLICKME"
    ]
    
    Polyglots = [
        "javascript://%250Aalert(1)//\"/*\\'/*\\'/*\"/*\\'/*\"/*] /*/ */ <!--></Title/</Style/</Script/--> <img src=x onerror=alert(1)//>"
    ]
    
    NOSQL_INJECTION = [
        {"$ne": 1},
        {"$gt": ""},
        {"$where": "sleep(100)"},
        {"$or": [{"a": 1}, {"b": 1}]}
    ]
    
    CMD_INJECTION = [
        "; ls -la",
        "| cat /etc/passwd",
        "& ping -c 10 127.0.0.1",
        "`whoami`",
        "$(whoami)",
        "; netstat -a"
    ]

    @staticmethod
    def get_all_string_payloads():
        return PayloadFactory.SQL_INJECTION + PayloadFactory.XSS_PAYLOADS + PayloadFactory.CMD_INJECTION + PayloadFactory.Polyglots
