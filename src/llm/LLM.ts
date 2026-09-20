import { DEFAULT_LLM_ATTRIBUTES, LLMAttributes, LLMMessage, LLMProvider, LLMToolDefinition } from './types';

export interface LLMResponse {
  content: string;
  raw?: unknown;
  usage?: {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
  };
}

/**
 * Representa el componente LLM de HUGIN: el motor de razonamiento
 * y generación de respuestas, con todos sus atributos configurables.
 */
export class LLM implements LLMAttributes {
  provider: LLMProvider;
  model: string;
  apiKey?: string;
  baseUrl?: string;
  organizationId?: string;

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

  contextWindow: number;
  memoryEnabled: boolean;

  tools?: LLMToolDefinition[];
  toolChoice?: string;

  stream: boolean;
  timeoutMs: number;
  maxRetries: number;

  metadata?: Record<string, unknown>;

  constructor(attributes: Partial<LLMAttributes> & Pick<LLMAttributes, 'provider' | 'model'>) {
    const merged: LLMAttributes = { ...DEFAULT_LLM_ATTRIBUTES, ...attributes };

    this.provider = merged.provider;
    this.model = merged.model;
    this.apiKey = merged.apiKey;
    this.baseUrl = merged.baseUrl;
    this.organizationId = merged.organizationId;

    this.systemPrompt = merged.systemPrompt;
    this.temperature = merged.temperature;
    this.topP = merged.topP;
    this.topK = merged.topK;
    this.maxTokens = merged.maxTokens;
    this.minTokens = merged.minTokens;
    this.stopSequences = merged.stopSequences;
    this.frequencyPenalty = merged.frequencyPenalty;
    this.presencePenalty = merged.presencePenalty;
    this.seed = merged.seed;

    this.contextWindow = merged.contextWindow;
    this.memoryEnabled = merged.memoryEnabled;

    this.tools = merged.tools;
    this.toolChoice = merged.toolChoice;

    this.stream = merged.stream;
    this.timeoutMs = merged.timeoutMs;
    this.maxRetries = merged.maxRetries;

    this.metadata = merged.metadata;
  }

  /** Devuelve una copia inmutable de todos los atributos actuales. */
  getAttributes(): LLMAttributes {
    return {
      provider: this.provider,
      model: this.model,
      apiKey: this.apiKey,
      baseUrl: this.baseUrl,
      organizationId: this.organizationId,
      systemPrompt: this.systemPrompt,
      temperature: this.temperature,
      topP: this.topP,
      topK: this.topK,
      maxTokens: this.maxTokens,
      minTokens: this.minTokens,
      stopSequences: this.stopSequences,
      frequencyPenalty: this.frequencyPenalty,
      presencePenalty: this.presencePenalty,
      seed: this.seed,
      contextWindow: this.contextWindow,
      memoryEnabled: this.memoryEnabled,
      tools: this.tools,
      toolChoice: this.toolChoice,
      stream: this.stream,
      timeoutMs: this.timeoutMs,
      maxRetries: this.maxRetries,
      metadata: this.metadata,
    };
  }

  /** Actualiza uno o varios atributos y devuelve la instancia (encadenable). */
  configure(partial: Partial<LLMAttributes>): this {
    Object.assign(this, partial);
    return this;
  }

  /**
   * Punto de integración con el proveedor real. La implementación concreta
   * de cada proveedor debe inyectarse aquí (adapter pattern) cuando se
   * conecte HUGIN a un SDK real (Anthropic, OpenAI, etc.).
   */
  async generate(_messages: LLMMessage[]): Promise<LLMResponse> {
    throw new Error(
      `LLM.generate() no está implementado para el proveedor "${this.provider}". ` +
        'Conecta un adapter concreto antes de usarlo.',
    );
  }
}
