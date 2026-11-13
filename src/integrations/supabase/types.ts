export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.18"
  }
  public: {
    Tables: {
      analysis_artifacts: {
        Row: {
          audio_events: Json
          frame_paths: Json
          model: string | null
          project_id: string
          provider: string | null
          scenes: Json
          summary: string | null
          transcript: Json
          updated_at: string
          warnings: Json
          waveform: Json
        }
        Insert: {
          audio_events?: Json
          frame_paths?: Json
          model?: string | null
          project_id: string
          provider?: string | null
          scenes?: Json
          summary?: string | null
          transcript?: Json
          updated_at?: string
          warnings?: Json
          waveform?: Json
        }
        Update: {
          audio_events?: Json
          frame_paths?: Json
          model?: string | null
          project_id?: string
          provider?: string | null
          scenes?: Json
          summary?: string | null
          transcript?: Json
          updated_at?: string
          warnings?: Json
          waveform?: Json
        }
        Relationships: [
          {
            foreignKeyName: "analysis_artifacts_project_id_fkey"
            columns: ["project_id"]
            isOneToOne: true
            referencedRelation: "projects"
            referencedColumns: ["id"]
          },
        ]
      }
      brand_settings: {
        Row: {
          owner_id: string
          settings: Json
          updated_at: string
        }
        Insert: {
          owner_id: string
          settings?: Json
          updated_at?: string
        }
        Update: {
          owner_id?: string
          settings?: Json
          updated_at?: string
        }
        Relationships: []
      }
      clips: {
        Row: {
          created_at: string
          edit: Json
          highlight_id: string
          id: string
          output_bytes: number
          output_path: string | null
          project_id: string
          render_status: string
          rendered_revision: number | null
          revision: number
          updated_at: string
        }
        Insert: {
          created_at?: string
          edit: Json
          highlight_id: string
          id?: string
          output_bytes?: number
          output_path?: string | null
          project_id: string
          render_status?: string
          rendered_revision?: number | null
          revision?: number
          updated_at?: string
        }
        Update: {
          created_at?: string
          edit?: Json
          highlight_id?: string
          id?: string
          output_bytes?: number
          output_path?: string | null
          project_id?: string
          render_status?: string
          rendered_revision?: number | null
          revision?: number
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "clips_highlight_id_project_id_fkey"
            columns: ["highlight_id", "project_id"]
            isOneToOne: false
            referencedRelation: "highlights"
            referencedColumns: ["id", "project_id"]
          },
          {
            foreignKeyName: "clips_project_id_fkey"
            columns: ["project_id"]
            isOneToOne: false
            referencedRelation: "projects"
            referencedColumns: ["id"]
          },
        ]
      }
      conversation_messages: {
        Row: {
          content: string
          created_at: string
          highlight_ids: string[]
          id: string
          project_id: string
          role: string
        }
        Insert: {
          content: string
          created_at?: string
          highlight_ids?: string[]
          id?: string
          project_id: string
          role: string
        }
        Update: {
          content?: string
          created_at?: string
          highlight_ids?: string[]
          id?: string
          project_id?: string
          role?: string
        }
        Relationships: [
          {
            foreignKeyName: "conversation_messages_project_id_fkey"
            columns: ["project_id"]
            isOneToOne: false
            referencedRelation: "projects"
            referencedColumns: ["id"]
          },
        ]
      }
      highlights: {
        Row: {
          category: string
          created_at: string
          end_time: number
          evidence: Json
          explanation: string
          id: string
          project_id: string
          score: number
          start_time: number
          title: string
        }
        Insert: {
          category: string
          created_at?: string
          end_time: number
          evidence?: Json
          explanation: string
          id?: string
          project_id: string
          score: number
          start_time: number
          title: string
        }
        Update: {
          category?: string
          created_at?: string
          end_time?: number
          evidence?: Json
          explanation?: string
          id?: string
          project_id?: string
          score?: number
          start_time?: number
          title?: string
        }
        Relationships: [
          {
            foreignKeyName: "highlights_project_id_fkey"
            columns: ["project_id"]
            isOneToOne: false
            referencedRelation: "projects"
            referencedColumns: ["id"]
          },
        ]
      }
      processing_jobs: {
        Row: {
          attempts: number
          cancel_requested: boolean
          clip_id: string | null
          created_at: string
          dedupe_key: string
          error: string | null
          id: string
          kind: string
          lease_token: string | null
          lease_until: string | null
          message_id: number | null
          payload: Json
          progress: number
          project_id: string
          reserved_bytes: number
          stage: string
          status: string
          updated_at: string
        }
        Insert: {
          attempts?: number
          cancel_requested?: boolean
          clip_id?: string | null
          created_at?: string
          dedupe_key: string
          error?: string | null
          id?: string
          kind: string
          lease_token?: string | null
          lease_until?: string | null
          message_id?: number | null
          payload?: Json
          progress?: number
          project_id: string
          reserved_bytes?: number
          stage?: string
          status?: string
          updated_at?: string
        }
        Update: {
          attempts?: number
          cancel_requested?: boolean
          clip_id?: string | null
          created_at?: string
          dedupe_key?: string
          error?: string | null
          id?: string
          kind?: string
          lease_token?: string | null
          lease_until?: string | null
          message_id?: number | null
          payload?: Json
          progress?: number
          project_id?: string
          reserved_bytes?: number
          stage?: string
          status?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "processing_jobs_clip_id_project_id_fkey"
            columns: ["clip_id", "project_id"]
            isOneToOne: false
            referencedRelation: "clips"
            referencedColumns: ["id", "project_id"]
          },
          {
            foreignKeyName: "processing_jobs_project_id_fkey"
            columns: ["project_id"]
            isOneToOne: false
            referencedRelation: "projects"
            referencedColumns: ["id"]
          },
        ]
      }
      profiles: {
        Row: {
          avatar_url: string | null
          created_at: string
          display_name: string
          id: string
          preferences: Json
        }
        Insert: {
          avatar_url?: string | null
          created_at?: string
          display_name?: string
          id: string
          preferences?: Json
        }
        Update: {
          avatar_url?: string | null
          created_at?: string
          display_name?: string
          id?: string
          preferences?: Json
        }
        Relationships: []
      }
      projects: {
        Row: {
          created_at: string
          deleted_at: string | null
          folder: string
          id: string
          instructions: string
          owner_id: string
          request_id: string
          source_platform: string
          source_url: string | null
          status: string
          title: string
          updated_at: string
        }
        Insert: {
          created_at?: string
          deleted_at?: string | null
          folder?: string
          id?: string
          instructions: string
          owner_id: string
          request_id: string
          source_platform?: string
          source_url?: string | null
          status?: string
          title: string
          updated_at?: string
        }
        Update: {
          created_at?: string
          deleted_at?: string | null
          folder?: string
          id?: string
          instructions?: string
          owner_id?: string
          request_id?: string
          source_platform?: string
          source_url?: string | null
          status?: string
          title?: string
          updated_at?: string
        }
        Relationships: []
      }
      provider_usage: {
        Row: {
          created_at: string
          estimated_cost: number
          id: string
          input_tokens: number
          job_id: string
          model: string
          output_tokens: number
          project_id: string
          provider: string
          request_key: string
          status: string
        }
        Insert: {
          created_at?: string
          estimated_cost?: number
          id?: string
          input_tokens?: number
          job_id: string
          model: string
          output_tokens?: number
          project_id: string
          provider: string
          request_key: string
          status?: string
        }
        Update: {
          created_at?: string
          estimated_cost?: number
          id?: string
          input_tokens?: number
          job_id?: string
          model?: string
          output_tokens?: number
          project_id?: string
          provider?: string
          request_key?: string
          status?: string
        }
        Relationships: [
          {
            foreignKeyName: "provider_usage_job_id_fkey"
            columns: ["job_id"]
            isOneToOne: false
            referencedRelation: "processing_jobs"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "provider_usage_project_id_fkey"
            columns: ["project_id"]
            isOneToOne: false
            referencedRelation: "projects"
            referencedColumns: ["id"]
          },
        ]
      }
      videos: {
        Row: {
          byte_size: number
          created_at: string
          duration: number | null
          filename: string
          fps: number | null
          has_audio: boolean | null
          height: number | null
          id: string
          mime_type: string
          playback_path: string | null
          project_id: string
          source_hash: string | null
          source_path: string
          status: string
          thumbnail_path: string | null
          width: number | null
        }
        Insert: {
          byte_size: number
          created_at?: string
          duration?: number | null
          filename: string
          fps?: number | null
          has_audio?: boolean | null
          height?: number | null
          id?: string
          mime_type: string
          playback_path?: string | null
          project_id: string
          source_hash?: string | null
          source_path: string
          status?: string
          thumbnail_path?: string | null
          width?: number | null
        }
        Update: {
          byte_size?: number
          created_at?: string
          duration?: number | null
          filename?: string
          fps?: number | null
          has_audio?: boolean | null
          height?: number | null
          id?: string
          mime_type?: string
          playback_path?: string | null
          project_id?: string
          source_hash?: string | null
          source_path?: string
          status?: string
          thumbnail_path?: string | null
          width?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "videos_project_id_fkey"
            columns: ["project_id"]
            isOneToOne: true
            referencedRelation: "projects"
            referencedColumns: ["id"]
          },
        ]
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      cancel_job: { Args: { jid: string }; Returns: undefined }
      export_clip: {
        Args: { cid: string; expected_revision: number }
        Returns: string
      }
      finalize_upload: { Args: { pid: string }; Returns: string }
      pipeline_health: { Args: never; Returns: Json }
      prepare_upload: {
        Args: {
          byte_size: number
          filename: string
          instructions: string
          mime_type: string
          request_id: string
        }
        Returns: Json
      }
      reserve_inference: {
        Args: {
          daily_limit: number
          jid: string
          model: string
          request_key: string
          token: string
        }
        Returns: string
      }
      retry_job: { Args: { jid: string }; Returns: string }
      save_clip: {
        Args: { edit: Json; expected_revision?: number; hid: string }
        Returns: string
      }
      set_deleted: {
        Args: { deleted: boolean; pid: string }
        Returns: undefined
      }
      worker_claim: { Args: never; Returns: Json }
      worker_finish_analysis: {
        Args: {
          artifacts: Json
          highlights: Json
          jid: string
          metadata: Json
          token: string
        }
        Returns: undefined
      }
      worker_finish_render: {
        Args: { bytes: number; jid: string; path: string; token: string }
        Returns: undefined
      }
      worker_heartbeat: {
        Args: { ai_ready: boolean; detail: string }
        Returns: undefined
      }
      worker_tick: {
        Args: {
          detail: string
          error_message?: string
          jid: string
          pct: number
          state: string
          token: string
        }
        Returns: boolean
      }
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends (DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never) = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends (PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never) = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {},
  },
} as const

