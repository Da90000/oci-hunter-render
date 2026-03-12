import subprocess
import time
import os
import requests
from datetime import datetime, timezone

COMPARTMENT_ID = os.environ['OCI_TENANCY']
USER = os.environ['OCI_USER']
FINGERPRINT = os.environ['OCI_FINGERPRINT']
REGION = os.environ['OCI_REGION']
PRIVATE_KEY = os.environ['OCI_PRIVATE_KEY']
SSH_PUBLIC_KEY = os.environ['OCI_SSH_PUBLIC_KEY']
TELEGRAM_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
TELEGRAM_CHAT_ID = os.environ['TELEGRAM_CHAT_ID']

RETRY_INTERVAL = 60
HOME = os.path.expanduser("~")
OCI_DIR = os.path.join(HOME, '.oci')
OCI_KEY = os.path.join(OCI_DIR, 'oci_api_key.pem')
OCI_CONFIG = os.path.join(OCI_DIR, 'config')

def setup_oci():
    os.makedirs(OCI_DIR, exist_ok=True)
    
    # Fix newlines in private key (env vars can strip them)
    private_key = PRIVATE_KEY.replace('\\n', '\n')
    
    # Ensure proper PEM format
    if '-----BEGIN' in private_key and '\n' not in private_key.split('-----BEGIN')[1][:10]:
        # Key is all on one line, needs reformatting
        private_key = private_key.replace(' ', '\n')
        private_key = private_key.replace('-----BEGIN\nRSA\nPRIVATE\nKEY-----', '-----BEGIN RSA PRIVATE KEY-----')
        private_key = private_key.replace('-----END\nRSA\nPRIVATE\nKEY-----', '-----END RSA PRIVATE KEY-----')
    
    with open(OCI_KEY, 'w') as f:
        f.write(private_key)
        if not private_key.endswith('\n'):
            f.write('\n')
    os.chmod(OCI_KEY, 0o600)
    
    config = f"""[DEFAULT]
user={USER}
fingerprint={FINGERPRINT}
tenancy={COMPARTMENT_ID}
region={REGION}
key_file={OCI_KEY}
"""
    with open(OCI_CONFIG, 'w') as f:
        f.write(config)
    os.chmod(OCI_CONFIG, 0o600)
    
    # Verify key file
    with open(OCI_KEY, 'r') as f:
        content = f.read()
    print(f"✅ OCI configured at {OCI_DIR}")
    print(f"   Key lines: {len(content.splitlines())}")
    print(f"   Key starts: {content[:30]}")

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message
        }, timeout=10)
        print(f"📱 Telegram sent: {message[:60]}...")
    except Exception as e:
        print(f"Telegram error: {e}")

def try_create_instance():
    ssh_key_file = '/tmp/ssh_key.pub'
    with open(ssh_key_file, 'w') as f:
        f.write(SSH_PUBLIC_KEY)

    env = os.environ.copy()
    env['OCI_CLI_SUPPRESS_FILE_PERMISSIONS_WARNING'] = 'True'
    env['SUPPRESS_LABEL_WARNING'] = 'True'

    # Use oci installed via pip (available as module)
    cmd = [
        '/app/.venv/bin/oci', 'compute', 'instance', 'launch',
        '--compartment-id', COMPARTMENT_ID,
        '--availability-domain', 'fOzi:AP-MUMBAI-1-AD-1',
        '--shape', 'VM.Standard.A1.Flex',
        '--shape-config', '{"ocpus": 4, "memoryInGBs": 24}',
        '--subnet-id', 'ocid1.subnet.oc1.ap-mumbai-1.aaaaaaaaxckerdunekrhnxdhdpshekiozbgdtojv2yd7y2nhgmg3trissjeq',
        '--assign-public-ip', 'true',
        '--display-name', 'n8n-free-instance',
        '--ssh-authorized-keys-file', ssh_key_file,
        '--source-details', '{"sourceType":"bootVolume","bootVolumeId":"ocid1.bootvolume.oc1.ap-mumbai-1.abrg6ljr3s7unrot74hlo4i33kmseigkdcyfwvnq5dq2yikhhhrqpucx5xwa"}',
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=120)
    return result.stdout + result.stderr

def main():
    print("=" * 50)
    print("🚀 VORTEX OCI Hunter — Railway.app")
    print(f"   Home: {HOME}")
    print("=" * 50)

    setup_oci()

    send_telegram(
        "🚀 OCI Hunter started on Railway.app!\n"
        "Checking every 60 seconds until instance is created.\n"
        "Region: AP-MUMBAI-1\n"
        "Shape: A1.Flex 4CPU/24GB"
    )

    attempt = 1
    while True:
        now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        print(f"\n[{now}] Attempt #{attempt}...")

        try:
            result = try_create_instance()
            print(result[:500])

            if '"lifecycle-state"' in result:
                print("\n✅ SUCCESS! Instance created!")
                send_telegram(
                    "✅ OCI Instance Created!\n\n"
                    "Shape: A1.Flex 4CPU/24GB\n"
                    "Boot: n8n old volume attached\n"
                    "Region: AP-MUMBAI-1\n\n"
                    "Go to OCI Console to get the IP!\n"
                    "Then SSH in and verify n8n is running!"
                )
                while True:
                    print("✅ Hunter complete. Sleeping...")
                    time.sleep(3600)

            elif 'Out of host capacity' in result:
                print(f"❌ Out of capacity. Waiting {RETRY_INTERVAL}s...")

            elif 'QuotaExceeded' in result or 'bootVolumeQuota' in result:
                print("❌ Quota exceeded!")
                send_telegram("⚠️ OCI Quota Exceeded! Check OCI Console.")
                time.sleep(300)

            elif 'NotAuthenticated' in result or 'InvalidParameter' in result:
                print("❌ Auth error!")
                send_telegram("❌ OCI Auth Error! Check environment variables.")
                time.sleep(600)

            else:
                print(f"❌ Unknown: {result[:300]}")

        except subprocess.TimeoutExpired:
            print("⏱️ Timed out — retrying...")
        except Exception as e:
            print(f"❌ Exception: {e}")

        attempt += 1
        time.sleep(RETRY_INTERVAL)

if __name__ == '__main__':
    main()
