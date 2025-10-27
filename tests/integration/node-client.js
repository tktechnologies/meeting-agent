const axios = require('axios');
const http = require('http');
const https = require('https');

// Configuração
const DEEPRESEARCH_URL = process.env.DEEPRESEARCH_URL || 'http://localhost:8000';
const MEETING_AGENT_URL = process.env.MEETING_AGENT_URL || 'http://localhost:8001';

// Configuração global de timeouts mais generosos
axios.defaults.timeout = 30000; // 30s padrão para requisições normais
axios.defaults.httpAgent = new http.Agent({ keepAlive: true });
axios.defaults.httpsAgent = new https.Agent({ keepAlive: true });

/**
 * Helper: Retry com exponential backoff
 */
async function retryRequest(requestFn, maxRetries = 3, initialDelay = 1000) {
  let lastError;
  
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await requestFn();
    } catch (error) {
      lastError = error;
      
      // Não retry em erros 4xx (cliente)
      if (error.response && error.response.status >= 400 && error.response.status < 500) {
        throw error;
      }
      
      // Retry em erros de rede ou 5xx
      if (i < maxRetries - 1) {
        const delay = initialDelay * Math.pow(2, i);
        console.log(`   ⚠️  Tentativa ${i + 1} falhou, aguardando ${delay}ms antes de retry...`);
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }
  
  throw lastError;
}

/**
 * Teste 1: Health Checks
 */
async function testHealthChecks() {
  console.log('\n🏥 TESTE 1: Health Checks\n');
  
  try {
    const drHealth = await axios.get(`${DEEPRESEARCH_URL}/health`);
    console.log('✅ Deep Research:', JSON.stringify(drHealth.data, null, 2));
    
    const maHealth = await axios.get(`${MEETING_AGENT_URL}/health`);
    console.log('✅ Meeting Agent:', JSON.stringify(maHealth.data, null, 2));
    
    return true;
  } catch (error) {
    console.error('❌ Health check falhou:', error.message);
    return false;
  }
}

/**
 * Teste 2: Deep Research Standalone (usando /research/async)
 */
async function testDeepResearch() {
  console.log('\n🔍 TESTE 2: Deep Research Standalone\n');
  
  try {
    const startTime = Date.now();
    
    // 1. Iniciar pesquisa assíncrona com tópico SIMPLES e RÁPIDO
    const asyncResponse = await axios.post(`${DEEPRESEARCH_URL}/research/async`, {
      topic: 'What is Python programming language',  // Tópico simples para teste rápido
      model_provider: 'gemini',
      thread_id: 'node-test-001'
    });
    
    const jobId = asyncResponse.data.job_id;
    console.log(`🚀 Job iniciado: ${jobId}`);
    
    // 2. Polling até concluir - AUMENTADO para 10 minutos
    let jobStatus;
    let attempts = 0;
    const maxAttempts = 120; // 10 minutos com polling de 5s
    
    while (attempts < maxAttempts) {
      await new Promise(resolve => setTimeout(resolve, 5000)); // Aguardar 5s
      
      try {
        // Usar retry para polling (resiliente a falhas temporárias)
        const statusResponse = await retryRequest(
          () => axios.get(`${DEEPRESEARCH_URL}/research/${jobId}`, { timeout: 10000 }),
          2,  // 2 retries
          2000  // 2s delay inicial
        );
        jobStatus = statusResponse.data;
        
        console.log(`   Status: ${jobStatus.status}... (tentativa ${attempts + 1}/${maxAttempts})`);
        
        if (jobStatus.status === 'completed') {
          break;
        } else if (jobStatus.status === 'failed') {
          throw new Error(`Job falhou: ${jobStatus.error}`);
        }
      } catch (pollError) {
        // Se polling falhou após retries, aguardar mais e tentar novamente
        console.log(`   ⚠️  Polling falhou (${pollError.message}), tentando novamente...`);
        if (attempts > 10) {
          // Após 10 tentativas (50 segundos), desistir
          throw pollError;
        }
      }
      
      attempts++;
    }
    
    if (!jobStatus || jobStatus.status !== 'completed') {
      throw new Error('Job timeout após 10 minutos');
    }
    
    const duration = ((Date.now() - startTime) / 1000).toFixed(1);
    const result = jobStatus.result;
    
    console.log('✅ Pesquisa concluída!');
    console.log(`   Duration: ${duration}s`);
    console.log(`   Steps: ${result.steps_completed}`);
    console.log(`   Quality: ${result.avg_quality.toFixed(1)}`);
    console.log(`   Model: ${result.model_provider}`);
    console.log(`   Report length: ${result.report.length} chars`);
    console.log(`   Report preview:\n   ${result.report.substring(0, 150)}...`);
    
    return result;
  } catch (error) {
    console.error('❌ Pesquisa falhou:', error.message);
    if (error.response) {
      console.error('   Status:', error.response.status);
      console.error('   Data:', JSON.stringify(error.response.data, null, 2));
    }
    return null;
  }
}

/**
 * Teste 3: Meeting Agent sem Deep Research (rápido)
 */
async function testMeetingAgentQuick() {
  console.log('\n📅 TESTE 3: Meeting Agent - Rápido (sem Deep Research)\n');
  
  try {
    const startTime = Date.now();
    const response = await axios.post(`${MEETING_AGENT_URL}/agenda/plan-nl`, {
      text: 'Create a quick team sync meeting about project status',
      org: 'org_node_test',
      language: 'en',
      format: 'json'
    }, {
      timeout: 60000 // 1 minuto
    });
    
    const duration = ((Date.now() - startTime) / 1000).toFixed(1);
    const data = response.data;
    
    console.log('✅ Agenda criada!');
    console.log(`   Duration: ${duration}s`);
    console.log(`   Subject: ${data.subject || 'N/A'}`);
    console.log(`   Sections: ${data.proposal?.agenda?.sections?.length || 0}`);
    console.log(`   Status: ${data.status || response.status}`);
    
    return data;
  } catch (error) {
    console.error('❌ Agenda creation falhou:', error.message);
    if (error.response) {
      console.error('   Status:', error.response.status);
      console.error('   Data:', JSON.stringify(error.response.data, null, 2));
    }
    return null;
  }
}

/**
 * Teste 4: Integração Completa (Meeting + Deep Research)
 * 
 * NOTA: Este teste demonstra como o orquestrador chat-agent-main deve integrar.
 * O Meeting Agent não chama Deep Research diretamente, o orquestrador faz:
 * 1. Orquestrador recebe requisição do usuário
 * 2. Orquestrador decide se precisa de Deep Research (baseado em intent/keywords)
 * 3. Se sim: Chama Deep Research → Recebe contexto enriquecido → Injeta no Meeting Agent
 * 4. Se não: Chama Meeting Agent diretamente
 */
async function testFullIntegration() {
  console.log('\n🔗 TESTE 4: Integração Completa (Meeting + Deep Research)\n');
  console.log('⚠️  Este teste pode demorar 5-10 minutos...\n');
  
  try {
    const totalStartTime = Date.now();
    
    // PASSO 1: Executar Deep Research com tópico SIMPLES
    console.log('🔍 PASSO 1/2: Executando Deep Research...');
    const researchStartTime = Date.now();
    
    const asyncResponse = await axios.post(`${DEEPRESEARCH_URL}/research/async`, {
      topic: 'Best practices for team meetings',  // Tópico simples e relevante
      model_provider: 'gemini',
      thread_id: 'node-integration-test'
    });
    
    const jobId = asyncResponse.data.job_id;
    console.log(`   Job iniciado: ${jobId}`);
    
    // Polling até concluir - AUMENTADO para 10 minutos
    let jobStatus;
    let attempts = 0;
    const maxAttempts = 120; // 10 minutos
    
    while (attempts < maxAttempts) {
      await new Promise(resolve => setTimeout(resolve, 5000));
      
      try {
        const statusResponse = await retryRequest(
          () => axios.get(`${DEEPRESEARCH_URL}/research/${jobId}`, { timeout: 10000 }),
          2,
          2000
        );
        jobStatus = statusResponse.data;
        
        if (attempts % 6 === 0) {
          // Log a cada 30 segundos
          console.log(`   Status: ${jobStatus.status}... (${Math.floor(attempts * 5 / 60)}m ${(attempts * 5) % 60}s)`);
        }
        
        if (jobStatus.status === 'completed') break;
        if (jobStatus.status === 'failed') throw new Error(`Research failed: ${jobStatus.error}`);
      } catch (pollError) {
        if (attempts > 10) throw pollError;
        console.log(`   ⚠️  Polling falhou (${pollError.message}), tentando novamente...`);
      }
      
      attempts++;
    }
    
    if (!jobStatus || jobStatus.status !== 'completed') {
      throw new Error('Research timeout após 10 minutos');
    }
    
    const researchDuration = ((Date.now() - researchStartTime) / 1000).toFixed(1);
    const researchResult = jobStatus.result;
    
    console.log(`✅ Deep Research concluída (${researchDuration}s)`);
    console.log(`   Quality: ${researchResult.avg_quality.toFixed(1)}`);
    console.log(`   Report: ${researchResult.report.length} chars`);
    
    // PASSO 2: Criar agenda com contexto enriquecido
    console.log('\n📅 PASSO 2/2: Criando agenda com contexto Deep Research...');
    const agendaStartTime = Date.now();
    
    // Preparar contexto enriquecido para o Meeting Agent
    const enrichedContext = `Deep Research Findings:\n\n${researchResult.report.substring(0, 1000)}...`;
    
    const agendaResponse = await axios.post(`${MEETING_AGENT_URL}/agenda/plan-nl`, {
      text: 'Create meeting about team collaboration best practices',  // Tópico simplificado
      org: 'org_integration_test',
      context: enrichedContext, // Injetar contexto do Deep Research
      language: 'en',
      duration_minutes: 45,  // Reduzido de 60 para 45
      format: 'json'
    }, {
      timeout: 180000  // 3 minutos (aumentado de 2)
    });
    
    const agendaDuration = ((Date.now() - agendaStartTime) / 1000).toFixed(1);
    const agendaData = agendaResponse.data;
    
    console.log(`✅ Agenda criada (${agendaDuration}s)`);
    console.log(`   Subject: ${agendaData.subject || 'N/A'}`);
    console.log(`   Sections: ${agendaData.proposal?.agenda?.sections?.length || 0}`);
    
    // RESUMO FINAL
    const totalDuration = ((Date.now() - totalStartTime) / 1000).toFixed(1);
    console.log(`\n🎉 Integração completa!`);
    console.log(`   Total duration: ${totalDuration}s`);
    console.log(`   Deep Research: ${researchDuration}s (${researchResult.steps_completed} steps)`);
    console.log(`   Agenda creation: ${agendaDuration}s`);
    console.log(`   Quality boost: ${researchResult.avg_quality.toFixed(1)}/5.0`);
    
    return {
      success: true,
      total_duration: totalDuration,
      deep_research: researchResult,
      agenda: agendaData,
      workflow: {
        step_1_research: `${researchDuration}s`,
        step_2_agenda: `${agendaDuration}s`
      }
    };
  } catch (error) {
    console.error('❌ Integração falhou:', error.message);
    if (error.response) {
      console.error('   Status:', error.response.status);
      console.error('   Data:', JSON.stringify(error.response.data, null, 2));
    }
    return null;
  }
}

/**
 * Executar todos os testes
 */
async function runAllTests() {
  console.log('╔════════════════════════════════════════════════════════╗');
  console.log('║   TESTES DE INTEGRAÇÃO - Node.js Client               ║');
  console.log('║   Deep Research + Meeting Agent                        ║');
  console.log('╚════════════════════════════════════════════════════════╝');
  
  const results = {
    health: await testHealthChecks(),
    deepresearch: await testDeepResearch(),
    meeting_quick: await testMeetingAgentQuick(),
    integration: await testFullIntegration()
  };
  
  console.log('\n╔════════════════════════════════════════════════════════╗');
  console.log('║   RESUMO DOS TESTES                                    ║');
  console.log('╚════════════════════════════════════════════════════════╝\n');
  
  console.log(`✓ Health Checks:          ${results.health ? '✅ PASS' : '❌ FAIL'}`);
  console.log(`✓ Deep Research:          ${results.deepresearch ? '✅ PASS' : '❌ FAIL'}`);
  console.log(`✓ Meeting Agent (quick):  ${results.meeting_quick ? '✅ PASS' : '❌ FAIL'}`);
  console.log(`✓ Integration (full):     ${results.integration ? '✅ PASS' : '❌ FAIL'}`);
  
  const passed = Object.values(results).filter(r => r).length;
  console.log(`\n📊 Total: ${passed}/4 testes passaram\n`);
  
  return passed === 4 ? 0 : 1;
}

// Executar
if (require.main === module) {
  runAllTests()
    .then(exitCode => process.exit(exitCode))
    .catch(err => {
      console.error('❌ Erro fatal:', err);
      process.exit(1);
    });
}

module.exports = {
  testHealthChecks,
  testDeepResearch,
  testMeetingAgentQuick,
  testFullIntegration
};
