import os, sys
from dotenv import dotenv_values
cfg = dotenv_values(".env")
import paramiko

host, port, user = cfg["SFTP_HOST"], int(cfg.get("SFTP_PORT", 22)), cfg["SFTP_USER"]
for label, pwd in (("SFTP_PASS", cfg.get("SFTP_PASS")), ("SSH_PASSWORD", cfg.get("SSH_PASSWORD"))):
    if not pwd:
        continue
    try:
        t = paramiko.Transport((host, port))
        t.banner_timeout = 30
        t.connect(username=user, password=pwd)
        sftp = paramiko.SFTPClient.from_transport(t)
        print(f"{label}: AUTH OK -> cwd={sftp.normalize('.')}")
        remote = cfg["REMOTE_DIR"]
        try:
            print("   REMOTE_DIR exists:", sftp.stat(remote) is not None)
            print("   entries:", [e.filename for e in sftp.listdir_attr(remote)][:8])
        except IOError as e:
            print("   REMOTE_DIR missing:", e)
        sftp.close(); t.close()
        break
    except Exception as e:
        print(f"{label}: FAIL {type(e).__name__}: {e}")