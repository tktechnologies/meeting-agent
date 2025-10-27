/**
 * TESTE SIMPLIFICADO - Apenas Health Checks
 * 
 * Use este teste quando os servidores estiverem instáveis.
 * Valida apenas que ambos estão respondendo HTTP.
 */

const axios = require('axios');

const DEEPRESEARCH_URL = process.env.DEEPRESEARCH_URL || 'http://localhost:8000';
const MEETING_AGENT_URL = process.env.MEETING_AGENT_URL || 'http://localhost:8001';

async function testHealth() {
  console.log('\n╔══════════════════════════════════════╗');
  console.log('║  TESTE SIMPLIFICADO - Health Checks  ║');
  console.log('╚══════════════════════════════════════╝\n');
  
  let passed = 0;
  let failed = 0;
  
  // Test 1: Deep Research Health
  try {
    const dr = await axios.get(`${DEEPRESEARCH_URL}/health`, { timeout: 10000 });
    console.log('✅ Deep Research (8000): ONLINE');
    console.log(`   Version: ${dr.data.version}`);
    console.log(`   Agent Ready: ${dr.data.agent_ready}`);
    console.log(`   Status: ${dr.data.status}\n`);
    passed++;
  } catch (error) {
    console.log('❌ Deep Research (8000): OFFLINE');
    console.log(`   Error: ${error.code || error.message}\n`);
    failed++;
  }
  
  // Test 2: Meeting Agent Health
  try {
    const ma = await axios.get(`${MEETING_AGENT_URL}/health`, { timeout: 10000 });
    console.log('✅ Meeting Agent (8001): ONLINE');
    console.log(`   Status: ${JSON.stringify(ma.data)}\n`);
    passed++;
  } catch (error) {
    console.log('❌ Meeting Agent (8001): OFFLINE');
    console.log(`   Error: ${error.code || error.message}\n`);
    failed++;
  }
  
  // Test 3: Deep Research Docs (Swagger UI)
  try {
    const docs = await axios.get(`${DEEPRESEARCH_URL}/docs`, { timeout: 5000 });
    if (docs.status === 200) {
      console.log('✅ Deep Research API Docs: Accessible\n');
      passed++;
    }
  } catch (error) {
    console.log('❌ Deep Research API Docs: Not accessible\n');
    failed++;
  }
  
  // Summary
  console.log('═══════════════════════════════════════');
  console.log(`📊 RESULTADO: ${passed}/${passed + failed} testes passaram`);
  console.log('═══════════════════════════════════════\n');
  
  if (failed > 0) {
    console.log('⚠️  SERVIDORES OFFLINE! Reinicie-os antes de testar:');
    console.log('\n   Deep Research (porta 8000):');
    console.log('   cd deepresearch-agent');
    console.log('   .\\venv\\Scripts\\Activate.ps1');
    console.log('   python -m uvicorn api.main:app --host 0.0.0.0 --port 8000\n');
    console.log('   Meeting Agent (porta 8001):');
    console.log('   cd meeting-agent-main');
    console.log('   .\\venv\\Scripts\\Activate.ps1');
    console.log('   python -m uvicorn agent.api:app --host 0.0.0.0 --port 8001\n');
  } else {
    console.log('🎉 TODOS OS SERVIDORES ONLINE! Pronto para testes de integração.\n');
  }
  
  process.exit(failed > 0 ? 1 : 0);
}

testHealth().catch(error => {
  console.error('\n❌ Erro fatal:', error.message);
  process.exit(1);
});
