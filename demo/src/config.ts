import { readFileSync } from 'node:fs';
import { parse as parseTOML } from 'smol-toml';

export interface LlmProviderConfig {
  apiKeyEnv: string;
  model: string;
  baseUrl: string;
}

export interface LlmConfig {
  conversationProvider: string;
  conversationModel: string;
  extractionProvider: string;
  extractionModel: string;
  openai: LlmProviderConfig;
}

export interface HebbsConfig {
  address: string;
}

export interface DemoConfig {
  llm: LlmConfig;
  hebbs: HebbsConfig;
}

export function defaultConfig(): DemoConfig {
  return {
    llm: {
      conversationProvider: 'openai',
      conversationModel: 'gpt-4o',
      extractionProvider: 'openai',
      extractionModel: 'gpt-4o-mini',
      openai: { apiKeyEnv: 'OPENAI_API_KEY', model: 'gpt-4o', baseUrl: '' },
    },
    hebbs: { address: 'localhost:6380' },
  };
}

export function loadConfig(path: string): DemoConfig {
  const raw = readFileSync(path, 'utf-8');
  const data = parseTOML(raw) as Record<string, unknown>;
  const cfg = defaultConfig();

  const llm = data['llm'] as Record<string, unknown> | undefined;
  if (llm) {
    if (llm['conversation_provider']) cfg.llm.conversationProvider = String(llm['conversation_provider']);
    if (llm['conversation_model']) cfg.llm.conversationModel = String(llm['conversation_model']);
    if (llm['extraction_provider']) cfg.llm.extractionProvider = String(llm['extraction_provider']);
    if (llm['extraction_model']) cfg.llm.extractionModel = String(llm['extraction_model']);
    const openai = llm['openai'] as Record<string, unknown> | undefined;
    if (openai) {
      if (openai['api_key_env']) cfg.llm.openai.apiKeyEnv = String(openai['api_key_env']);
      if (openai['model']) cfg.llm.openai.model = String(openai['model']);
    }
  }

  const hebbs = data['hebbs'] as Record<string, unknown> | undefined;
  if (hebbs) {
    if (hebbs['address']) cfg.hebbs.address = String(hebbs['address']);
  }

  return cfg;
}

export function getApiKey(cfg: DemoConfig): string | undefined {
  const envName = cfg.llm.openai.apiKeyEnv;
  return envName ? process.env[envName] : undefined;
}
