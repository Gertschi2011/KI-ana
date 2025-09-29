import os, json, hashlib, io
from minio import Minio
from dotenv import load_dotenv
load_dotenv()

endpoint=os.getenv("MINIO_ENDPOINT","localhost:9000")
ak=os.getenv("MINIO_ACCESS_KEY","minio")
sk=os.getenv("MINIO_SECRET_KEY","minio123")
bucket=os.getenv("MINIO_BUCKET","artifacts")
secure=os.getenv("MINIO_SECURE","false").lower()=="true"

m=Minio(endpoint, access_key=ak, secret_key=sk, secure=secure)
if not m.bucket_exists(bucket):
    m.make_bucket(bucket)

payload={"numbers":[1,2,3,4]}
b=json.dumps(payload).encode()
cid=hashlib.sha256(b).hexdigest()
key=f"artifacts/{cid}"
m.put_object(bucket, key, io.BytesIO(b), length=len(b))
print(cid)
