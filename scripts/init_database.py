"""
Inicializa o banco de dados SQLite com as tabelas necessárias
"""

import sys
import os
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
from datetime import datetime

def get_db_path():
    """Get SQLite database path"""
    # Try to get from config
    try:
        from agent.config import DB_PATH
        return DB_PATH
    except:
        # Fallback to default
        return "spine_dev.sqlite3"

def init_database():
    """Initialize SQLite database with required tables"""
    
    db_path = get_db_path()
    
    print(f"\n{'='*80}")
    print(f"🗄️  INICIALIZANDO BANCO DE DADOS SQLITE")
    print(f"{'='*80}\n")
    print(f"📁 Caminho: {db_path}\n")
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check existing tables
    print("1️⃣  Verificando tabelas existentes...")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = [row[0] for row in cursor.fetchall()]
    print(f"   Tabelas encontradas: {existing_tables if existing_tables else 'Nenhuma'}\n")
    
    # Create orgs table (MUST be first - referenced by facts)
    print("2️⃣  Criando tabela 'orgs'...")
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orgs (
                org_id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE
            )
        """)
        print("   ✅ Tabela 'orgs' criada/verificada\n")
    except Exception as e:
        print(f"   ❌ Erro ao criar tabela 'orgs': {e}\n")
        return False
    
    # Create facts table
    print("3️⃣  Criando tabela 'facts'...")
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS facts (
                fact_id TEXT PRIMARY KEY,
                org_id TEXT NOT NULL,
                meeting_id TEXT,
                transcript_id TEXT,
                fact_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'proposed',
                confidence REAL,
                payload TEXT NOT NULL,
                due_iso TEXT,
                due_at DATETIME,
                idempotency_key TEXT UNIQUE,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        """)
        print("   ✅ Tabela 'facts' criada/verificada\n")
    except Exception as e:
        print(f"   ❌ Erro ao criar tabela 'facts': {e}\n")
        return False
    
    # Create indexes for facts
    print("4️⃣  Criando índices para 'facts'...")
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_facts_org_id ON facts(org_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_facts_type ON facts(fact_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_facts_status ON facts(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_facts_created ON facts(created_at)")
        print("   ✅ Índices criados\n")
    except Exception as e:
        print(f"   ❌ Erro ao criar índices: {e}\n")
    
    # Create FTS table for full-text search
    print("5️⃣  Criando tabela FTS 'facts_fts'...")
    try:
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
                fact_id UNINDEXED,
                org_id UNINDEXED,
                content,
                tokenize='porter unicode61'
            )
        """)
        print("   ✅ Tabela FTS 'facts_fts' criada\n")
    except Exception as e:
        print(f"   ❌ Erro ao criar tabela FTS: {e}\n")
    
    # Create workstreams table (if needed)
    print("6️⃣  Criando tabela 'workstreams'...")
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workstreams (
                workstream_id TEXT PRIMARY KEY,
                org_id TEXT NOT NULL,
                name TEXT,
                description TEXT,
                status TEXT,
                created_at TEXT,
                updated_at TEXT,
                metadata TEXT
            )
        """)
        print("   ✅ Tabela 'workstreams' criada/verificada\n")
    except Exception as e:
        print(f"   ❌ Erro ao criar tabela 'workstreams': {e}\n")
    
    # Create fact_workstream junction table
    print("7️⃣  Criando tabela de junção 'fact_workstream'...")
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fact_workstream (
                fact_id TEXT,
                workstream_id TEXT,
                PRIMARY KEY (fact_id, workstream_id),
                FOREIGN KEY (fact_id) REFERENCES facts(fact_id),
                FOREIGN KEY (workstream_id) REFERENCES workstreams(workstream_id)
            )
        """)
        print("   ✅ Tabela 'fact_workstream' criada/verificada\n")
    except Exception as e:
        print(f"   ❌ Erro ao criar tabela fact_workstream: {e}\n")
    
    # Commit changes
    conn.commit()
    
    # Verify tables were created
    print("8️⃣  Verificando tabelas criadas...")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    all_tables = [row[0] for row in cursor.fetchall()]
    print(f"   Tabelas no banco:")
    for table in all_tables:
        print(f"      - {table}")
    print()
    
    # Insert sample org and fact for testing
    print("9️⃣  Inserindo dados de teste...")
    try:
        test_fact_id = "fact_test_init"
        test_org_id = "org_test"
        test_timestamp = datetime.utcnow().isoformat()
        
        # Insert test org FIRST
        cursor.execute("""
            INSERT OR IGNORE INTO orgs (org_id, name)
            VALUES (?, ?)
        """, (test_org_id, "Test Organization"))
        
        # Insert into facts table (matching db.py schema)
        cursor.execute("""
            INSERT OR REPLACE INTO facts 
            (fact_id, org_id, fact_type, payload, confidence, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            test_fact_id,
            test_org_id,
            "test",
            json.dumps({"content": "Este é um fact de teste para validar a inicialização do banco de dados."}),
            1.0,
            "published",
            test_timestamp,
            test_timestamp
        ))
        
        # Insert into FTS
        cursor.execute("""
            INSERT OR REPLACE INTO facts_fts (fact_id, org_id, content)
            VALUES (?, ?, ?)
        """, (
            test_fact_id,
            test_org_id,
            "Este é um fact de teste para validar a inicialização do banco de dados."
        ))
        
        conn.commit()
        print(f"   ✅ Org de teste: {test_org_id}")
        print(f"   ✅ Fact de teste: {test_fact_id}\n")
        
    except Exception as e:
        print(f"   ⚠️  Não foi possível inserir fact de teste: {e}\n")
    
    # Count facts
    print("🔟  Contando dados no banco...")
    try:
        org_count = cursor.execute("SELECT COUNT(*) FROM orgs").fetchone()[0]
        print(f"   📊 Total de orgs: {org_count}")
        
        count = cursor.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        print(f"   📊 Total de facts: {count}")
        
        fts_count = cursor.execute("SELECT COUNT(*) FROM facts_fts").fetchone()[0]
        print(f"   📊 Total de facts_fts: {fts_count}\n")
        
    except Exception as e:
        print(f"   ⚠️  Erro ao contar: {e}\n")
    
    # Close connection
    conn.close()
    
    print(f"{'='*80}")
    print(f"✅ BANCO DE DADOS INICIALIZADO COM SUCESSO!")
    print(f"{'='*80}\n")
    
    print(f"🎯 Próximos passos:")
    print(f"   1. Execute novamente os testes do retriever")
    print(f"   2. Execute os testes E2E")
    print(f"   3. Deep Research agora deve ser acionado quando houver < 8 facts\n")
    
    return True


if __name__ == "__main__":
    try:
        success = init_database()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
