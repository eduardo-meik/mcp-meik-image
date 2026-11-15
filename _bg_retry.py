import time
from dotenv import dotenv_values
import paramiko
cfg = dotenv_values(".env")
pkey = paramiko.PKey.from_path("meik_media_key")
for intento in range(1, 4):
    espera = 300 if intento > 1 else 300
    time.sleep(espera)
    try:
        t = paramiko.Transport((cfg["SFTP_HOST"], 22)); t.banner_timeout = 40
        t.connect(username=cfg["SFTP_USER"], pkey=pkey)
        sftp = paramiko.SFTPClient.from_transport(t)
        print(f"intento {intento}: CONECTADO home={sftp.normalize('.')}", flush=True)
        try:
            print("REMOTE_DIR:", [e.filename for e in sftp.listdir_attr(cfg['REMOTE_DIR'])][:8], flush=True)
        except IOError:
            print("REMOTE_DIR no existe (se crearia)", flush=True)
        sftp.close(); t.close()
        break
    except paramiko.AuthenticationException:
        print(f"intento {intento}: clave rechazada (no autorizada aun)", flush=True)
    except Exception as e:
        print(f"intento {intento}: {type(e).__name__}: {str(e)[:100]}", flush=True)