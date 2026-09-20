export type LLMProvider = 'anthropic' | 'openai' | 'google' | 'mistral' | 'ollama' | 'custom';

export type LLMRole = 'system' | 'user' | 'assistant' | 'tool';

export interface LLMMessage {
  role: LLMRole;
  content: string;
  name?: string;
}

export interface LLMToolDefinition {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
}

export interface LLMAttributes {
  // Identidad / proveedor
  provider: LLMProvider;
  model: string;
  apiKey?: string;
  baseUrl?: string;
  organizationId?: string;

  // Generación
  systemPrompt?: string;
  temperature: number;
  topP: number;
  topK?: number;
  maxTokens: number;
  minTokens?: number;
  stopSequences?: string[];
  frequencyPenalty?: number;
  presencePenalty?: number;
  seed?: number;

  // Contexto
  contextWindow: number;
  memoryEnabled: boolean;

  // Herramientas / agentes
  tools?: LLMToolDefinition[];
  toolChoice?: 'auto' | 'none' | 'required' | string;

  // Comportamiento de red
  stream: boolean;
  timeoutMs: number;
  maxRetries: number;

  // Extensión
  metadata?: Record<string, unknown>;
}

export const DEFAULT_LLM_ATTRIBUTES: Omit<LLMAttributes, 'provider' | 'model'> = {
  temperature: 0.7,
  topP: 1,
  maxTokens: 1024,
  contextWindow: 8192,
  memoryEnabled: true,
  stream: false,
  timeoutMs: 30000,
  maxRetries: 2,
};
