#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""login-range —— 登录页攻击靶场（12 个漏洞，本地可打）"""
import argparse, base64, hashlib, json, os, random, sqlite3, threading, time
import traceback, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DB = "/tmp/login_range.db"
LOCK = threading.Lock()
SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT UNIQUE, pw TEXT,
 role TEXT, reset_token TEXT, remember TEXT, tfa TEXT, fail INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS sessions(sid TEXT PRIMARY KEY, user TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY, msg TEXT, ts REAL);
"""

def db():
    c = sqlite3.connect(DB, timeout=10); c.row_factory = sqlite3.Row; return c

def init():
    with LOCK:
        c = db(); c.executescript(SCHEMA)
        c.execute("DELETE FROM users"); c.execute("DELETE FROM sessions"); c.execute("DELETE FROM logs")
        for n,p,r in [("admin","Adm1n!2024","admin"),("alice","Summer2024!","user"),
                      ("bob","P@ssw0rd1","user"),("carol","qwerty123","user"),
                      ("dave","Dave#2023","user"),("svc","s3rv1ce","service")]:
            c.execute("INSERT INTO users(name,pw,role,reset_token,remember,tfa) VALUES(?,?,?,?,?,?)",
                (n,p,r,f"rt-{n}-{random.randint(1000,9999)}",
                 base64.b64encode(f"{n}:{p}".encode()).decode(),"000000"))
        c.commit(); c.close()

class H(BaseHTTPRequestHandler):
    protocol_version="HTTP/1.1"
    def log_message(self,*a): pass
    def _send(self,code,body,ct="application/json; charset=utf-8",extra=None):
        if isinstance(body,(dict,list)): body=json.dumps(body,ensure_ascii=False)
        b=body.encode() if isinstance(body,str) else body
        self.send_response(code); self.send_header("Content-Type",ct)
        self.send_header("Content-Length",str(len(b)))
        for k,v in (extra or {}).items(): self.send_header(k,v)
        self.end_headers(); self.wfile.write(b)
    def _body(self):
        n=int(self.headers.get("Content-Length") or 0); raw=self.rfile.read(n) if n else b""
        ct=self.headers.get("Content-Type","")
        if "json" in ct:
            try: return json.loads(raw or b"{}")
            except: return {}
        return {k:v[0] for k,v in urllib.parse.parse_qs(raw.decode("utf-8","replace")).items()}

    def v1(self,d):
        c=db(); r=c.execute("SELECT * FROM users WHERE name=?",(d.get("u",""),)).fetchone()
        if not r: c.close(); return self._send(401,{"error":"user not found"})
        if r["pw"]!=d.get("p",""):
            c.execute("UPDATE users SET fail=fail+1 WHERE name=?",(r["name"],)); c.commit(); c.close()
            return self._send(401,{"error":"wrong password"})
        c.close(); return self._send(200,{"ok":True,"role":r["role"]})

    def v2(self,d):
        c=db(); r=c.execute("SELECT * FROM users WHERE name=?",(d.get("u",""),)).fetchone(); c.close()
        if not r: return self._send(401,{"error":"bad"})
        p=d.get("p",""); real=r["pw"]
        for i,ch in enumerate(p):
            if i>=len(real) or ch!=real[i]: return self._send(401,{"error":"bad"})
            time.sleep(0.02)
        if len(p)!=len(real): return self._send(401,{"error":"bad"})
        return self._send(200,{"ok":True,"role":r["role"]})

    def v3(self,d):
        sql=f"SELECT * FROM users WHERE name='{d.get('u','')}' AND pw='{d.get('p','')}'"
        try:
            c=db(); r=c.execute(sql).fetchone(); c.close()
        except Exception as e:
            return self._send(500,{"error":f"SQL error: {e}"})
        if r: return self._send(200,{"ok":True,"role":r["role"],"injected":True})
        return self._send(401,{"error":"bad"})

    def v4(self,d):
        c=db(); r=c.execute("SELECT * FROM users WHERE name=?",(d.get("u",""),)).fetchone()
        if r and r["pw"]==d.get("p",""):
            c.close(); return self._send(200,{"ok":True,"role":r["role"]})
        if r:
            c.execute("UPDATE users SET fail=fail+1 WHERE name=?",(r["name"],)); c.commit()
        c.close(); return self._send(401,{"error":"bad"})

    def v5(self,d):
        try: raw=base64.b64decode(d.get("token","")).decode()
        except: return self._send(400,{"error":"bad token"})
        if ":" not in raw: return self._send(400,{"error":"bad token"})
        u,p=raw.split(":",1)
        return self._send(200,{"ok":True,"user":u,"decoded":raw,"note":"明文 base64 可伪造"})

    def v6(self,d):
        c=db(); r=c.execute("SELECT * FROM users WHERE name=?",(d.get("u",""),)).fetchone(); c.close()
        if not r: return self._send(404,{"error":"no user"})
        return self._send(200,{"sent":True,"token":r["reset_token"],"note":"rt-<user>-<4位>"})

    def v6do(self,d):
        c=db(); r=c.execute("SELECT * FROM users WHERE reset_token=?",(d.get("token",""),)).fetchone()
        if not r: c.close(); return self._send(400,{"error":"bad token"})
        c.execute("UPDATE users SET pw=? WHERE name=?",(d.get("p",""),r["name"])); c.commit(); c.close()
        return self._send(200,{"ok":True,"user":r["name"],"pw":d.get("p","")})

    def v7(self,d):
        sid=d.get("sid") or "attacker-chosen"; u=d.get("u","alice")
        c=db(); c.execute("INSERT OR REPLACE INTO sessions(sid,user,ts) VALUES(?,?,?)",(sid,u,time.time()))
        c.commit(); c.close()
        return self._send(200,{"ok":True,"sid":sid,"user":u,"note":"不重新生成 sid"})

    def v7who(self,d):
        c=db(); r=c.execute("SELECT * FROM sessions WHERE sid=?",(d.get("sid",""),)).fetchone(); c.close()
        if not r: return self._send(401,{"error":"no session"})
        return self._send(200,{"user":r["user"],"hijacked":True})

    def v8(self,d):
        c=db(); r=c.execute("SELECT * FROM users WHERE name=?",(d.get("u",""),)).fetchone(); c.close()
        if not r: return self._send(404,{"error":"no user"})
        if d.get("code")=="000000": return self._send(200,{"ok":True,"user":r["name"],"note":"万能码"})
        if d.get("code")==r["tfa"]: return self._send(200,{"ok":True,"user":r["name"]})
        return self._send(401,{"error":"bad code"})

    def v9(self,d):
        c=db(); c.execute("UPDATE users SET role=? WHERE name=?",(d.get("role","user"),d.get("u",""))); c.commit(); c.close()
        return self._send(200,{"ok":True,"user":d.get("u"),"role":d.get("role"),"note":"无权限校验"})

    def v10(self,d):
        c=db(); rows=c.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 50").fetchall(); c.close()
        return self._send(200,{"logs":[{"msg":r["msg"],"ts":r["ts"]} for r in rows]})

    def v11(self,d):
        c=db(); c.execute("INSERT INTO logs(msg,ts) VALUES(?,?)",
            (f"transfer {d.get('u')} -> {d.get('amt')} (no csrf)",time.time())); c.commit(); c.close()
        return self._send(200,{"ok":True,"note":"无 CSRF token"})

    def v12(self,d):
        try: return self._send(200,{"ok":True,"v":1/int(d.get("n","0"))})
        except Exception as e:
            return self._send(500,{"error":str(e),
                "trace":traceback.format_exc().splitlines()[-5:],"note":"堆栈泄露"})

    def do_GET(self):
        u=urllib.parse.urlparse(self.path); p=u.path
        q={k:v[0] for k,v in urllib.parse.parse_qs(u.query).items()}
        if p=="/": return self._send(200,{"range":"login-range","vulns":12,
            "endpoints":["/v1/login","/v2/login","/v3/login","/v4/login","/v5/remember",
                         "/v6/reset","/v6/reset/do","/v7/fix","/v7/who","/v8/tfa",
                         "/v9/role","/v10/logs","/v11/transfer","/v12/debug"]})
        if p=="/v6/reset": return self.v6(q)
        if p=="/v7/who": return self.v7who(q)
        if p=="/v10/logs": return self.v10(q)
        return self._send(404,{"error":"not found"})

    def do_POST(self):
        p=urllib.parse.urlparse(self.path).path; d=self._body()
        R={"/v1/login":self.v1,"/v2/login":self.v2,"/v3/login":self.v3,"/v4/login":self.v4,
           "/v5/remember":self.v5,"/v6/reset/do":self.v6do,"/v7/fix":self.v7,
           "/v8/tfa":self.v8,"/v9/role":self.v9,"/v11/transfer":self.v11,"/v12/debug":self.v12}
        f=R.get(p)
        return f(d) if f else self._send(404,{"error":"not found"})

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--port",type=int,default=9100)
    a=ap.parse_args()
    if os.path.exists(DB): os.remove(DB)
    init()
    srv=ThreadingHTTPServer(("127.0.0.1",a.port),H)
    print(f"login-range: http://127.0.0.1:{a.port}/  (12 漏洞)")
    try: srv.serve_forever()
    except KeyboardInterrupt: print("\n[stop]")

if __name__=="__main__": main()
