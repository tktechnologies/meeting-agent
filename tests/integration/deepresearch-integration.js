const axios = require('axios');

/**
 * Cliente Deep Research para chat-agent-main orquestrador
 */
class DeepResearchClient {
  constructor(baseUrl = process.env.DEEPRESEARCH_API_URL || 'http://localhost:8000') {
    this.baseUrl = baseUrl;
    this.timeout = parseInt(process.env.DEEPRESEARCH_TIMEOUT || '300000'); // 5 min
    this.maxSteps = parseInt(process.env.DEEPRESEARCH_MAX_STEPS || '5');
  }

  /**
   * Health check
   */
  async healthCheck() {
    try {
      const response = await axios.get(`${this.baseUrl}/health`, {
        timeout: 5000
      });
      return response.data;
    } catch (error) {
      console.error('[DeepResearch] Health check failed:', error.message);
      return null;
    }
  }

  /**
   * Executar pesquisa profunda
   */
  async research(topic, options = {}) {
    const {
      modelProvider = 'openai',
      maxSteps = this.maxSteps,
      correlationId = null
    } = options;

    try {
      console.log(`[DeepResearch] Starting research: "${topic}"`);
      console.log(`[DeepResearch] Config: model=${modelProvider}, steps=${maxSteps}`);

      const startTime = Date.now();
      
      const response = await axios.post(`${this.baseUrl}/research`, {
        topic,
        model_provider: modelProvider,
        max_steps: maxSteps,
        correlation_id: correlationId
      }, {
        timeout: this.timeout
      });

      const duration = ((Date.now() - startTime) / 1000).toFixed(1);
      
      console.log(`[DeepResearch] Completed in ${duration}s`);
      console.log(`[DeepResearch] Quality: ${response.data.quality_score}/10`);
      console.log(`[DeepResearch] Steps: ${response.data.steps_taken}`);

      return {
        success: true,
        result: response.data.result,
        quality_score: response.data.quality_score,
        steps_taken: response.data.steps_taken,
        duration_seconds: parseFloat(duration),
        model_used: response.data.model_used
      };
    } catch (error) {
      console.error('[DeepResearch] Research failed:', error.message);
      
      if (error.code === 'ECONNABORTED') {
        return {
          success: false,
          error: 'timeout',
          message: 'Deep Research exceeded timeout'
        };
      }

      return {
        success: false,
        error: 'api_error',
        message: error.message
      };
    }
  }
}

/**
 * Cliente Meeting Agent para chat-agent-main orquestrador
 */
class MeetingAgentClient {
  constructor(baseUrl = process.env.MEETING_AGENT_URL || 'http://localhost:8001') {
    this.baseUrl = baseUrl;
    this.timeout = parseInt(process.env.MEETING_AGENT_TIMEOUT || '300000'); // 5 min
  }

  /**
   * Health check
   */
  async healthCheck() {
    try {
      const response = await axios.get(`${this.baseUrl}/health`, {
        timeout: 5000
      });
      return response.data;
    } catch (error) {
      console.error('[MeetingAgent] Health check failed:', error.message);
      return null;
    }
  }

  /**
   * Criar meeting com agenda
   */
  async createMeeting(query, options = {}) {
    const {
      orgId = 'default_org',
      userId = 'default_user',
      language = 'en',
      intent = null
    } = options;

    try {
      console.log(`[MeetingAgent] Creating meeting: "${query}"`);

      const startTime = Date.now();
      
      const response = await axios.post(`${this.baseUrl}/meetings/create`, {
        org_id: orgId,
        user_id: userId,
        raw_query: query,
        language,
        intent
      }, {
        timeout: this.timeout
      });

      const duration = ((Date.now() - startTime) / 1000).toFixed(1);
      
      console.log(`[MeetingAgent] Meeting created in ${duration}s`);
      console.log(`[MeetingAgent] Facts used: ${response.data.facts_used}`);
      console.log(`[MeetingAgent] Deep Research: ${response.data.deep_research_used || false}`);

      return {
        success: true,
        meeting_id: response.data.meeting_id,
        agenda: response.data.agenda,
        facts_used: response.data.facts_used,
        deep_research_used: response.data.deep_research_used || false,
        deep_research_quality: response.data.deep_research_quality,
        duration_seconds: parseFloat(duration)
      };
    } catch (error) {
      console.error('[MeetingAgent] Create meeting failed:', error.message);
      
      return {
        success: false,
        error: error.response?.status || 'api_error',
        message: error.message
      };
    }
  }
}

module.exports = {
  DeepResearchClient,
  MeetingAgentClient
};
