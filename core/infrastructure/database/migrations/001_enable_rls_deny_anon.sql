-- migration: 001_enable_rls_deny_anon
-- purpose: enable row-level security on all public tables and deny direct
--          rest api access to the anon role. the backend connects via psycopg2
--          as the postgres service role, which bypasses rls entirely, so
--          application behaviour is unaffected.
-- run: paste into supabase → sql editor → run

-- ── users ─────────────────────────────────────────────────────────────────────
alter table public.users enable row level security;

-- deny all direct rest api access for anonymous callers
create policy "deny anon select on users"
    on public.users for select
    to anon
    using (false);

create policy "deny anon insert on users"
    on public.users for insert
    to anon
    with check (false);

create policy "deny anon update on users"
    on public.users for update
    to anon
    using (false);

create policy "deny anon delete on users"
    on public.users for delete
    to anon
    using (false);

-- ── instances ─────────────────────────────────────────────────────────────────
alter table public.instances enable row level security;

create policy "deny anon select on instances"
    on public.instances for select
    to anon
    using (false);

create policy "deny anon insert on instances"
    on public.instances for insert
    to anon
    with check (false);

create policy "deny anon update on instances"
    on public.instances for update
    to anon
    using (false);

create policy "deny anon delete on instances"
    on public.instances for delete
    to anon
    using (false);

-- ── products ──────────────────────────────────────────────────────────────────
alter table public.products enable row level security;

create policy "deny anon select on products"
    on public.products for select
    to anon
    using (false);

create policy "deny anon insert on products"
    on public.products for insert
    to anon
    with check (false);

create policy "deny anon update on products"
    on public.products for update
    to anon
    using (false);

create policy "deny anon delete on products"
    on public.products for delete
    to anon
    using (false);

-- ── affiliate_configs ─────────────────────────────────────────────────────────
alter table public.affiliate_configs enable row level security;

create policy "deny anon select on affiliate_configs"
    on public.affiliate_configs for select
    to anon
    using (false);

create policy "deny anon insert on affiliate_configs"
    on public.affiliate_configs for insert
    to anon
    with check (false);

create policy "deny anon update on affiliate_configs"
    on public.affiliate_configs for update
    to anon
    using (false);

create policy "deny anon delete on affiliate_configs"
    on public.affiliate_configs for delete
    to anon
    using (false);
