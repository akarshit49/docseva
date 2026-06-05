//genai: Sprint 3 / WS-F — API response types mirroring Pydantic OUT schemas.

export interface UserOut {
  id: string
  organization_id: string
  name: string
  email: string | null
  phone: string | null
  role: string
  telegram_user_id: string | null
  created_at: string
}

export interface OrganizationOut {
  id: string
  name: string
  plan: string
  plan_status: string
  docs_used_this_cycle: number
  docs_limit_per_cycle: number
  created_at: string
}

export interface CompanyProfileOut {
  display_name: string | null
  address: string | null
  city: string | null
  state: string | null
  pincode: string | null
  gstin: string | null
  pan: string | null
  phone: string | null
  email: string | null
  website: string | null
  bank_name: string | null
  bank_account: string | null
  bank_ifsc: string | null
  logo_key: string | null
  logo_url: string | null
  invoice_prefix: string
  invoice_counter: number
  po_prefix: string
  po_counter: number
  quotation_prefix: string
  quotation_counter: number
}

export interface MeResponse {
  user: UserOut
  organization: OrganizationOut
  company_profile: CompanyProfileOut | null
}

export interface WebTokens {
  access_token: string
  refresh_token: string
  token_type: 'Bearer'
  expires_in: number
}

export interface WebAuthResponse {
  user: UserOut
  organization: OrganizationOut
  tokens: WebTokens
  is_new: boolean
}

export interface SisterFormatOut {
  id: string
  name: string
  original_filename: string
  file_key: string
  created_at: string
}

export interface DocumentOut {
  id: string
  feature: string
  status: string
  original_filename: string | null
  output_filename: string | null
  output_file_key: string | null
  input_file_key: string | null
  source_document_id: string | null
  document_type: string | null
  download_url: string | null
  created_at: string
  expires_at: string | null
}

export interface DocumentMetadataOut {
  id: string
  feature: string
  document_type: string | null
  parsed_data: Record<string, unknown>
  output_filename: string | null
  output_file_key: string | null
  created_at: string
}

export interface ProcessQuota {
  used: number
  limit: number
}

export interface ProcessResponse {
  document_id: string | null
  output_filename: string | null
  output_url: string | null
  input_url: string | null
  parsed_data: Record<string, unknown>
  needs_confirmation: boolean
  quota: ProcessQuota | null
}

export interface ChannelLinkOut {
  id: string
  channel: string
  handle: string
  verified_at: string | null
  created_at: string
}

export interface ChannelLinkStartResponse {
  channel: string
  token: string
  expires_in: number
  deep_link: string | null
}

// Parsed quote shape returned inside `ProcessResponse.parsed_data` for
// sister_quote / preview mode. Loose typing because the LLM controls it.
export interface QuoteItemPreview {
  sno: string
  description: string
  qty: string
  unit_price: number
  total: number
}
export interface QuoteSectionPreview {
  name: string
  items: QuoteItemPreview[]
}
export interface QuotePreview {
  recipient_name: string
  recipient_address_lines: string[]
  subject: string
  ref_no: string
  date: string
  valid_until: string
  sections: QuoteSectionPreview[]
  subtotal: number
}

export interface ApiErrorPayload {
  code: string
  user_message: string
  retryable: boolean
  details?: Record<string, unknown> | null
}
