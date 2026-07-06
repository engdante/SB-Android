/**
 * Централизиран модул за типове концепции и съобщения.
 * 
 * ЕДИНСТВЕН източник на истина: config/concept_types.json
 * Ако добавяш нов тип, промени само JSON файла — този модул го чете автоматично.
 */

// ══════════════════════════════════════════════════
// Зареждане от JSON конфиг
// ══════════════════════════════════════════════════

// Vite поддържа директен import на JSON
import config from '../../../config/concept_types.json';

interface ConceptTypesConfig {
    types: Record<string, string>;
    notifications: string[];
    api_statuses: string[];
    default_type: string;
}

const typedConfig = config as ConceptTypesConfig;

// ══════════════════════════════════════════════════
// OKF концепции (type поле)
// ══════════════════════════════════════════════════

export const CONCEPT_TYPES: string[] = Object.keys(typedConfig.types);

/** Default тип за нови концепции */
export const DEFAULT_CONCEPT_TYPE: string = typedConfig.default_type || CONCEPT_TYPES[2];

// ══════════════════════════════════════════════════
// Български описания за всеки тип
// ══════════════════════════════════════════════════

export const CONCEPT_TYPE_DESCRIPTIONS: Record<string, string> = { ...typedConfig.types };

// ══════════════════════════════════════════════════
// Типове за UI нотификации
// ══════════════════════════════════════════════════

export type NotificationType = 'success' | 'error' | 'warning' | 'info';

export const NOTIFICATION_TYPES: NotificationType[] = [...typedConfig.notifications] as NotificationType[];

// ══════════════════════════════════════════════════
// API response статуси
// ══════════════════════════════════════════════════

export type ApiStatusType = 'ok' | 'error' | 'warning';

export const API_STATUS_TYPES: ApiStatusType[] = [...typedConfig.api_statuses] as ApiStatusType[];

// ══════════════════════════════════════════════════
// Helper functions
// ══════════════════════════════════════════════════

/** Връща българското описание за даден тип концепция */
export function getConceptTypeDescription(type: string): string {
    return CONCEPT_TYPE_DESCRIPTIONS[type] || `${type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())} — автоматично`;
}

/** Проверява дали даден тип е валиден */
export function isValidConceptType(type: string): boolean {
    return CONCEPT_TYPES.includes(type);
}
