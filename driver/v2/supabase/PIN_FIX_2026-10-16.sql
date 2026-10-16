-- PIN fix of 16 Oct 2026, for a database set up before it. Paste all of it into the
-- Supabase SQL editor of the Pidi project and press Run. Safe to run twice.
-- Same four functions as in PIDI_SETUP.sql: many PIN tries at once now count one by
-- one (the lock after 5 misses holds), and a new kitchen PIN must be 6 to 8 digits.
-- A kitchen PIN set before this keeps working until it is changed.

begin;

-- A miss is returned as jsonb, not raised. A raised error would roll the failure
-- count back, and the lock would never stick. One kitchen, so the lock is global.
-- Tries wait in line for one another, so many tries at once still count one by one.
create or replace function public.pidi_kitchen_login(pin text)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  hash text;
  failures integer;
  locked timestamptz;
  token text;
  hours integer;
begin
  perform pg_advisory_xact_lock(hashtext('pidi-kitchen-login'));
  hash := public.pidi_setting('kitchen_pin_hash');
  if hash is null or hash = '' then
    return jsonb_build_object('ok', false, 'error', 'The kitchen PIN is not set yet.');
  end if;
  locked := nullif(public.pidi_setting('kitchen_pin_locked_until'), '')::timestamptz;
  if locked is not null and locked > now() then
    return jsonb_build_object('ok', false, 'error', 'Too many tries. Wait 5 minutes.');
  end if;
  if pin is null or pin !~ '^[0-9]{4,8}$'
     or extensions.crypt(pin, hash) is distinct from hash then
    failures := coalesce(public.pidi_setting('kitchen_pin_failures')::integer, 0) + 1;
    insert into public.pidi_settings (key, value) values ('kitchen_pin_failures', failures::text)
    on conflict (key) do update set value = excluded.value;
    if failures >= 5 then
      insert into public.pidi_settings (key, value)
      values ('kitchen_pin_locked_until', (now() + interval '5 minutes')::text)
      on conflict (key) do update set value = excluded.value;
    end if;
    return jsonb_build_object('ok', false, 'error', 'That PIN does not match.');
  end if;
  insert into public.pidi_settings (key, value) values ('kitchen_pin_failures', '0')
  on conflict (key) do update set value = '0';
  update public.pidi_settings set value = '' where key = 'kitchen_pin_locked_until';
  token := public.pidi_new_token();
  hours := coalesce(public.pidi_setting('session_hours')::integer, 12);
  insert into public.pidi_kitchen_sessions (token_hash, expires_at)
  values (extensions.crypt(token, extensions.gen_salt('bf', 8)), now() + make_interval(hours => hours));
  return jsonb_build_object(
    'ok', true,
    'token', token,
    'expires_at', now() + make_interval(hours => hours),
    'topic', public.pidi_kitchen_topic()
  );
end
$$;

-- Returns null when the PIN is good. A wrong PIN is returned as text, not raised:
-- a raised error would roll the failure count back, and the lock would never stick.
-- Tries wait in line for one another, so many tries at once still count one by one.
create or replace function public.pidi_admin_ok(admin_pin text)
returns text
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  hash text;
  failures integer;
  locked timestamptz;
begin
  perform pg_advisory_xact_lock(hashtext('pidi-admin-login'));
  hash := public.pidi_setting('admin_pin_hash');
  if hash is null or hash = '' then
    return 'Set the admin PIN in the SQL editor first. The seed is at the bottom of PIDI_SETUP.sql.';
  end if;
  locked := nullif(public.pidi_setting('admin_pin_locked_until'), '')::timestamptz;
  if locked is not null and locked > now() then
    return 'Too many tries. Wait 5 minutes.';
  end if;
  if admin_pin is null or admin_pin !~ '^[0-9]{8}$'
     or extensions.crypt(admin_pin, hash) is distinct from hash then
    failures := coalesce(public.pidi_setting('admin_pin_failures')::integer, 0) + 1;
    insert into public.pidi_settings (key, value) values ('admin_pin_failures', failures::text)
    on conflict (key) do update set value = excluded.value;
    if failures >= 5 then
      insert into public.pidi_settings (key, value)
      values ('admin_pin_locked_until', (now() + interval '5 minutes')::text)
      on conflict (key) do update set value = excluded.value;
    end if;
    return 'Admin PIN does not match.';
  end if;
  insert into public.pidi_settings (key, value) values ('admin_pin_failures', '0')
  on conflict (key) do update set value = '0';
  update public.pidi_settings set value = '' where key = 'admin_pin_locked_until';
  return null;
end
$$;

-- A new kitchen PIN is 6 to 8 digits. Sign in still takes 4 to 8, so a PIN set
-- before this rule keeps working until it is changed here.
create or replace function public.pidi_admin_set_kitchen_pin(admin_pin text, new_pin text)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  admin_msg text;
begin
  admin_msg := public.pidi_admin_ok(admin_pin);
  if admin_msg is not null then
    return jsonb_build_object('ok', false, 'error', admin_msg);
  end if;
  if new_pin is null or new_pin !~ '^[0-9]{6,8}$' then
    raise exception 'Kitchen PIN must be 6 to 8 digits.';
  end if;
  -- Waits for a kitchen sign-in in progress, so its miss is not counted on the new PIN.
  perform pg_advisory_xact_lock(hashtext('pidi-kitchen-login'));
  insert into public.pidi_settings (key, value)
  values ('kitchen_pin_hash', extensions.crypt(new_pin, extensions.gen_salt('bf', 8)))
  on conflict (key) do update set value = excluded.value;
  insert into public.pidi_settings (key, value) values ('kitchen_pin_failures', '0')
  on conflict (key) do update set value = '0';
  update public.pidi_settings set value = '' where key = 'kitchen_pin_locked_until';
  update public.pidi_kitchen_sessions set expires_at = now() where expires_at > now();
  return '{"ok":true}'::jsonb;
end
$$;

create or replace function public.pidi_driver_login(driver_name_or_id text, pin text)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  drv public.pidi_drivers%rowtype;
  token text;
  hours integer;
  key text;
begin
  key := lower(trim(coalesce(driver_name_or_id, '')));
  -- The driver's row stays locked until this try ends, so tries at once for one
  -- driver wait in line and count one by one.
  select * into drv
  from public.pidi_drivers d
  where d.active and (d.code = key or lower(d.name) = key or d.id::text = key)
  for no key update;
  if not found then
    return jsonb_build_object('ok', false, 'error', 'That PIN does not match.');
  end if;
  if drv.pin_locked_until is not null and drv.pin_locked_until > now() then
    return jsonb_build_object('ok', false, 'error', 'Too many tries. Wait 5 minutes.');
  end if;
  -- Returned, not raised: a raised error would roll this driver's count back.
  if pin is null or pin !~ '^[0-9]{4,8}$'
     or extensions.crypt(pin, drv.pin_hash) is distinct from drv.pin_hash then
    update public.pidi_drivers
      set pin_failures = pin_failures + 1,
          pin_locked_until = case when pin_failures + 1 >= 5 then now() + interval '5 minutes' else pin_locked_until end
      where id = drv.id;
    return jsonb_build_object('ok', false, 'error', 'That PIN does not match.');
  end if;
  update public.pidi_drivers
    set pin_failures = 0, pin_locked_until = null
    where id = drv.id;
  token := public.pidi_new_token();
  hours := coalesce(public.pidi_setting('session_hours')::integer, 12);
  insert into public.pidi_driver_sessions (driver_id, token_hash, expires_at)
  values (drv.id, extensions.crypt(token, extensions.gen_salt('bf', 8)), now() + make_interval(hours => hours));
  return jsonb_build_object(
    'ok', true,
    'token', token,
    'driver_id', drv.id,
    'name', drv.name,
    'topic', 'pidi:driver:' || drv.id::text,
    'expires_at', now() + make_interval(hours => hours)
  );
end
$$;

commit;
