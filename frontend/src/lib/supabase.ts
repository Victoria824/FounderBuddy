import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  console.warn('⚠️ Supabase environment variables are not set.');
  console.warn('Please add the following to frontend/.env.local:');
  console.warn('  NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co');
  console.warn('  NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key');
  console.warn('Tiptap editing will not work without these variables.');
}

export const supabase = supabaseUrl && supabaseAnonKey
  ? createClient(supabaseUrl, supabaseAnonKey)
  : null;

