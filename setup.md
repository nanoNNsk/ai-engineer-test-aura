# Quick Setup Guide

## ขั้นตอนการติดตั้งและรัน (5 นาทีเสร็จ)

### 1. รัน Docker Compose
```bash
cd src/infra
docker-compose up -d
```

คำสั่งนี้จะรัน:
- PostgreSQL 15 + pgvector extension (port 5432)
- Redis (port 6379)

### 2. ตรวจสอบว่า services รันอยู่
```bash
docker-compose ps
```

ควรเห็น postgres และ redis รันอยู่ (status: Up)

### 3. ติดตั้ง Python dependencies
```bash
cd ../backend
pip install -r requirements.txt
```

### 4. สร้างไฟล์ .env
```bash
# Windows
copy .env.example .env

# Linux/Mac
cp .env.example .env
```

**หมายเหตุ:** ไฟล์ .env มี DATABASE_URL และ REDIS_URL ตั้งค่าไว้แล้วสำหรับ Docker Compose
- ใส่ OpenAI API key ทีหลังก็ได้ (ถ้ายังไม่มี)

### 5. รัน Application
```bash
uvicorn main:app --reload
```

### 6. เปิดเบราว์เซอร์
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

---

## คำสั่งที่ใช้บ่อย

### หยุด services
```bash
cd src/infra
docker-compose down
```

### หยุดและลบข้อมูล
```bash
cd src/infra
docker-compose down -v
```

### ดู logs
```bash
cd src/infra
docker-compose logs -f
```

### เข้า PostgreSQL
```bash
docker exec -it rag_postgres psql -U postgres -d rag_system
```

### เข้า Redis CLI
```bash
docker exec -it rag_redis redis-cli
```

---

## ทดสอบระบบ (หลังใส่ OpenAI API key)

### 1. สร้าง Tenant
```bash
docker exec -it rag_postgres psql -U postgres -d rag_system -c "INSERT INTO tenants (id, name) VALUES (gen_random_uuid(), 'Test Company') RETURNING id;"
```

### 2. รัน Test Script
```bash
cd src/backend
python test_e2e.py
```

---

## Troubleshooting

**Port ชนกัน:**
- แก้ไข ports ใน src/infra/docker-compose.yml
- เช่น เปลี่ยน "5432:5432" เป็น "5433:5432"

**Docker ไม่รัน:**
- ตรวจสอบว่า Docker Desktop เปิดอยู่
- รัน: `docker --version` เพื่อเช็ค

**Database connection error:**
- รอ 10-15 วินาที หลัง docker-compose up
- ตรวจสอบ: `docker-compose logs postgres`
