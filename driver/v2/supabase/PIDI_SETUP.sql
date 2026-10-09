-- Pidi v2 setup. Paste this once into the Supabase SQL editor.
-- Project: the live bookkeeping database. This file is the only change.
--
-- It creates objects in public only, and every new name starts with pidi_:
-- tables, types, functions, triggers, indexes, and policies.
-- It does not enable extensions, create schemas, create roles, or change
-- default privileges. It does not drop, alter, grant, or revoke anything
-- whose name does not start with pidi_.
--
-- Needs these already present (Supabase has them). If they are missing,
-- this script stops. It will not enable them:
--   extensions.crypt, extensions.gen_salt, gen_random_uuid, and the anon role.
--
-- The only existing object it writes to is the publication supabase_realtime,
-- and only to add public.pidi_* tables that are not already members.
-- If that publication is absent, this step is skipped.
--
-- Broadcast: when realtime.send(jsonb, text, text, boolean) already exists,
-- triggers send a public ping {"ping":"changed"} on an unguessable topic.
-- No policy is added to realtime.messages. If send is missing or refused,
-- the order still saves. The apps poll every 8 seconds either way.
--
-- Safe to run twice. Pins are not in this file. After it succeeds, run the
-- commented seed at the bottom yourself, with PINs you choose.

do $pidi_need$
begin
  if to_regprocedure('extensions.crypt(text,text)') is null
     or to_regprocedure('extensions.gen_salt(text,integer)') is null
     or to_regprocedure('gen_random_uuid()') is null then
    raise exception 'Pidi needs extensions.crypt, extensions.gen_salt, and gen_random_uuid already installed. This script will not enable them.';
  end if;
  if not exists (select 1 from pg_roles where rolname = 'anon') then
    raise exception 'Pidi needs the existing anon role. This script will not create roles.';
  end if;
end
$pidi_need$;

do $pidi_types$
begin
  if not exists (select 1 from pg_type t join pg_namespace n on n.oid = t.typnamespace
                 where n.nspname = 'public' and t.typname = 'pidi_status') then
    create type public.pidi_status as enum (
      'new', 'accepted', 'cooking', 'ready', 'assigned', 'picked_up', 'delivered', 'cancelled'
    );
  end if;
  if not exists (select 1 from pg_type t join pg_namespace n on n.oid = t.typnamespace
                 where n.nspname = 'public' and t.typname = 'pidi_pay_method') then
    create type public.pidi_pay_method as enum ('cash', 'transfer');
  end if;
  if not exists (select 1 from pg_type t join pg_namespace n on n.oid = t.typnamespace
                 where n.nspname = 'public' and t.typname = 'pidi_transfer_status') then
    create type public.pidi_transfer_status as enum ('awaiting', 'paid');
  end if;
  if not exists (select 1 from pg_type t join pg_namespace n on n.oid = t.typnamespace
                 where n.nspname = 'public' and t.typname = 'pidi_run_status') then
    create type public.pidi_run_status as enum ('offered', 'active', 'done', 'cancelled');
  end if;
  if not exists (select 1 from pg_type t join pg_namespace n on n.oid = t.typnamespace
                 where n.nspname = 'public' and t.typname = 'pidi_offer_status') then
    create type public.pidi_offer_status as enum ('pending', 'accepted', 'declined', 'expired', 'lost');
  end if;
end
$pidi_types$;

create table if not exists public.pidi_restaurants (
  id uuid primary key default gen_random_uuid(),
  slug text not null,
  name text not null,
  partner boolean not null default false,
  active boolean not null default true,
  constraint pidi_restaurants_slug unique (slug)
);

create table if not exists public.pidi_settings (
  key text primary key,
  value text not null,
  constraint pidi_settings_key check (key ~ '^pidi_|^[a-z0-9_]+$')
);

create table if not exists public.pidi_drivers (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  phone text,
  code text not null,
  pin_hash text not null,
  online boolean not null default false,
  active boolean not null default true,
  pin_failures integer not null default 0,
  pin_locked_until timestamptz,
  constraint pidi_drivers_code unique (code)
);

create table if not exists public.pidi_orders (
  id uuid primary key default gen_random_uuid(),
  restaurant_id uuid not null references public.pidi_restaurants (id),
  public_token text not null,
  client_token text,
  status public.pidi_status not null default 'new',
  customer_name text not null,
  phone text not null,
  area text not null,
  address text not null,
  lat numeric,
  lng numeric,
  note text,
  pay public.pidi_pay_method not null,
  food_cents integer not null,
  fee_cents integer not null,
  pays_with_cents integer,
  change_due_cents integer generated always as (
    case when pay = 'cash' then pays_with_cents - (food_cents + fee_cents) else null end
  ) stored,
  transfer_status public.pidi_transfer_status,
  due_at timestamptz not null,
  outside_hours boolean not null default false,
  test boolean not null default false,
  created_at timestamptz not null default now(),
  constraint pidi_orders_token unique (public_token),
  constraint pidi_orders_client unique (client_token),
  constraint pidi_orders_money check (
    food_cents >= 0 and fee_cents >= 0
    and (
      (pay = 'cash' and pays_with_cents is not null and pays_with_cents >= food_cents + fee_cents and transfer_status is null)
      or (pay = 'transfer' and pays_with_cents is null and transfer_status is not null)
    )
  ),
  constraint pidi_orders_pin check ((lat is null and lng is null) or (lat is not null and lng is not null))
);

create table if not exists public.pidi_order_items (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.pidi_orders (id),
  name text not null,
  qty integer not null,
  price_cents integer not null,
  constraint pidi_order_items_qty check (qty > 0 and price_cents >= 0)
);

create table if not exists public.pidi_order_events (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.pidi_orders (id),
  status public.pidi_status not null,
  at timestamptz not null default now()
);

create table if not exists public.pidi_runs (
  id uuid primary key default gen_random_uuid(),
  status public.pidi_run_status not null default 'offered',
  driver_id uuid references public.pidi_drivers (id),
  created_at timestamptz not null default now()
);

create table if not exists public.pidi_run_orders (
  run_id uuid not null references public.pidi_runs (id),
  order_id uuid not null references public.pidi_orders (id),
  stop_index integer not null,
  constraint pidi_run_orders_pk primary key (run_id, stop_index),
  constraint pidi_run_orders_order unique (order_id),
  constraint pidi_run_orders_stop check (stop_index in (1, 2))
);

create table if not exists public.pidi_offers (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.pidi_runs (id),
  driver_id uuid not null references public.pidi_drivers (id),
  status public.pidi_offer_status not null default 'pending',
  expires_at timestamptz not null,
  created_at timestamptz not null default now()
);

create unique index if not exists pidi_offers_one_pending
  on public.pidi_offers (run_id, driver_id)
  where status = 'pending';

create table if not exists public.pidi_driver_locations (
  driver_id uuid primary key references public.pidi_drivers (id),
  lat numeric not null,
  lng numeric not null,
  at timestamptz not null default now()
);

create table if not exists public.pidi_kitchen_sessions (
  id uuid primary key default gen_random_uuid(),
  token_hash text not null,
  expires_at timestamptz not null
);

create table if not exists public.pidi_driver_sessions (
  id uuid primary key default gen_random_uuid(),
  driver_id uuid not null references public.pidi_drivers (id),
  token_hash text not null,
  expires_at timestamptz not null
);

insert into public.pidi_restaurants (slug, name, partner) values
  ('dushi-wok', 'Dushi Wok', false),
  ('taco-brava', 'Taco Brava', false),
  ('smash-shack', 'Smash Shack', false),
  ('nonnas-night-in', 'Nonna''s Night In', false),
  ('oranje-snack', 'Oranje Snack', false)
on conflict (slug) do nothing;

insert into public.pidi_settings (key, value) values
  ('dispatch_when', 'ready'),
  ('offer_seconds', '45'),
  ('pair_minutes', '10'),
  ('pair_km', '3'),
  ('fee_cents', '500'),
  ('min_food_cents', '2400'),
  ('hours_mode', 'reject'),
  ('location_seconds', '8'),
  ('session_hours', '12'),
  ('pickup_name', ''),
  ('pickup_address', ''),
  ('pickup_lat', ''),
  ('pickup_lng', '')
on conflict (key) do nothing;

create or replace function public.pidi_setting(p_key text)
returns text
language sql
stable
security definer
set search_path = public, extensions
as $$
  select value from public.pidi_settings where key = p_key
$$;

create or replace function public.pidi_km(lat1 numeric, lng1 numeric, lat2 numeric, lng2 numeric)
returns numeric
language sql
immutable
set search_path = public
as $$
  select case
    when lat1 is null or lng1 is null or lat2 is null or lng2 is null then null
    else round((6371 * 2 * asin(least(1::numeric, sqrt(
      power(sin(radians((lat2 - lat1) / 2)), 2)
      + cos(radians(lat1)) * cos(radians(lat2)) * power(sin(radians((lng2 - lng1) / 2)), 2)
    ))))::numeric, 3)
  end
$$;

create or replace function public.pidi_new_token()
returns text
language sql
volatile
security definer
set search_path = public, extensions
as $$
  select replace(gen_random_uuid()::text, '-', '') || replace(gen_random_uuid()::text, '-', '')
$$;

create or replace function public.pidi_kitchen_topic()
returns text
language plpgsql
volatile
security definer
set search_path = public, extensions
as $$
declare
  topic text;
begin
  select value into topic from public.pidi_settings where key = 'kitchen_topic';
  if topic is null or topic = '' then
    topic := 'pidi:k:' || public.pidi_new_token();
    insert into public.pidi_settings (key, value) values ('kitchen_topic', topic)
    on conflict (key) do nothing;
    select value into topic from public.pidi_settings where key = 'kitchen_topic';
  end if;
  return topic;
end
$$;

create or replace function public.pidi_broadcast(p_topic text)
returns void
language plpgsql
security definer
set search_path = public, extensions
as $$
begin
  if p_topic is null or p_topic = '' then
    return;
  end if;
  if to_regprocedure('realtime.send(jsonb,text,text,boolean)') is null then
    return;
  end if;
  perform realtime.send(
    jsonb_build_object('ping', 'changed'),
    'changed',
    p_topic,
    false
  );
exception when others then
  return;
end
$$;

create or replace function public.pidi_log(p_order uuid, p_status text)
returns void
language plpgsql
security definer
set search_path = public, extensions
as $$
begin
  insert into public.pidi_order_events (order_id, status)
  values (p_order, p_status::public.pidi_status);
end
$$;

create or replace function public.pidi_offer_run(p_run uuid, p_seconds integer)
returns void
language plpgsql
security definer
set search_path = public, extensions
as $$
begin
  insert into public.pidi_offers (run_id, driver_id, status, expires_at)
  select p_run, d.id, 'pending', now() + make_interval(secs => p_seconds)
  from public.pidi_drivers d
  where d.online and d.active
    and not exists (
      select 1 from public.pidi_runs r
      where r.driver_id = d.id and r.status = 'active'
    )
    and not exists (
      select 1 from public.pidi_offers o
      where o.run_id = p_run
        and o.driver_id = d.id
        and o.status in ('pending', 'accepted', 'declined')
    );
end
$$;

create or replace function public.pidi_dispatch()
returns void
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  when_status text;
  pair_min integer;
  pair_km numeric;
  offer_sec integer;
  ord record;
  mate_id uuid;
  host_run uuid;
  open_run uuid;
begin
  perform pg_advisory_xact_lock(hashtext('pidi-dispatch'));

  when_status := coalesce(public.pidi_setting('dispatch_when'), 'ready');
  if when_status not in ('ready', 'accepted') then
    when_status := 'ready';
  end if;
  pair_min := coalesce(public.pidi_setting('pair_minutes')::integer, 10);
  pair_km := coalesce(public.pidi_setting('pair_km')::numeric, 3);
  offer_sec := coalesce(public.pidi_setting('offer_seconds')::integer, 45);

  update public.pidi_offers
    set status = 'expired'
    where status = 'pending' and expires_at <= now();

  for ord in
    select o.*
    from public.pidi_orders o
    where (
      (when_status = 'ready' and o.status = 'ready')
      or (when_status = 'accepted' and o.status in ('accepted', 'cooking', 'ready'))
    )
    order by o.created_at
  loop
    if exists (
      select 1
      from public.pidi_run_orders ro
      join public.pidi_runs r on r.id = ro.run_id
      where ro.order_id = ord.id and r.status in ('offered', 'active')
    ) then
      continue;
    end if;

    host_run := null;
    select r.id into host_run
    from public.pidi_runs r
    join public.pidi_run_orders ro on ro.run_id = r.id and ro.stop_index = 1
    join public.pidi_orders first_stop on first_stop.id = ro.order_id
    where r.status = 'offered'
      and not exists (
        select 1 from public.pidi_run_orders x where x.run_id = r.id and x.stop_index = 2
      )
      and public.pidi_km(first_stop.lat, first_stop.lng, ord.lat, ord.lng) < pair_km
      and public.pidi_km(first_stop.lat, first_stop.lng, ord.lat, ord.lng) is not null
      and (
        ord.status = 'ready'
        or ord.due_at <= now() + make_interval(mins => pair_min)
      )
    order by r.created_at
    limit 1;

    if host_run is not null then
      insert into public.pidi_run_orders (run_id, order_id, stop_index)
      values (host_run, ord.id, 2);
      update public.pidi_offers set status = 'expired'
        where run_id = host_run and status = 'pending';
      perform public.pidi_offer_run(host_run, offer_sec);
      continue;
    end if;

    mate_id := null;
    select o2.id into mate_id
    from public.pidi_orders o2
    where o2.id <> ord.id
      and o2.status in ('accepted', 'cooking', 'ready')
      and not exists (
        select 1
        from public.pidi_run_orders ro
        join public.pidi_runs r on r.id = ro.run_id
        where ro.order_id = o2.id and r.status in ('offered', 'active')
      )
      and (
        o2.status = 'ready'
        or o2.due_at <= now() + make_interval(mins => pair_min)
      )
      and public.pidi_km(ord.lat, ord.lng, o2.lat, o2.lng) < pair_km
      and public.pidi_km(ord.lat, ord.lng, o2.lat, o2.lng) is not null
    order by o2.created_at
    limit 1;

    insert into public.pidi_runs (status) values ('offered') returning id into open_run;
    insert into public.pidi_run_orders (run_id, order_id, stop_index)
    values (open_run, ord.id, 1);
    if mate_id is not null then
      insert into public.pidi_run_orders (run_id, order_id, stop_index)
      values (open_run, mate_id, 2);
    end if;
    perform public.pidi_offer_run(open_run, offer_sec);
  end loop;

  for open_run in
    select r.id from public.pidi_runs r where r.status = 'offered'
  loop
    perform public.pidi_offer_run(open_run, offer_sec);
  end loop;
end
$$;

create or replace function public.pidi_ping()
returns jsonb
language sql
stable
security definer
set search_path = public, extensions
as $$
  select '{"ok":true}'::jsonb
$$;

create or replace function public.pidi_place_order(payload jsonb)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  rest_id uuid;
  rest_name text;
  food integer := 0;
  fee integer;
  minimum integer;
  item jsonb;
  qty integer;
  price integer;
  pay text;
  pays integer;
  v_lat numeric;
  v_lng numeric;
  v_due timestamptz;
  outside boolean := false;
  local_time time;
  hours text;
  token text;
  client_token text;
  existing jsonb;
  order_id uuid;
  uname text;
begin
  if payload is null or jsonb_typeof(payload) <> 'object' then
    raise exception 'Send the order as one object.';
  end if;
  if lower(coalesce(payload->>'pickup', '')) in ('true', '1', 'yes') then
    raise exception 'Delivery only.';
  end if;

  select id, name into rest_id, rest_name
  from public.pidi_restaurants
  where slug = lower(trim(coalesce(payload->>'restaurant', ''))) and active;
  if not found then
    raise exception 'That restaurant is not open for orders.';
  end if;

  uname := trim(coalesce(payload->>'name', ''));
  if uname = '' or trim(coalesce(payload->>'phone', '')) = ''
     or trim(coalesce(payload->>'area', '')) = ''
     or trim(coalesce(payload->>'address', '')) = '' then
    raise exception 'Name, phone, area, and address are required.';
  end if;
  if length(regexp_replace(payload->>'phone', '\D', '', 'g')) < 7 then
    raise exception 'Enter a phone number the driver can call.';
  end if;

  if jsonb_typeof(payload->'items') <> 'array' or jsonb_array_length(payload->'items') < 1 then
    raise exception 'Add at least one dish.';
  end if;
  for item in select value from jsonb_array_elements(payload->'items')
  loop
    qty := (item->>'qty')::integer;
    price := (item->>'price_cents')::integer;
    if qty is null or qty < 1 or qty > 20 or price is null or price < 0 or price > 100000
       or length(trim(coalesce(item->>'name', ''))) < 1 then
      raise exception 'Check the dishes and try again.';
    end if;
    food := food + qty * price;
  end loop;

  minimum := coalesce(public.pidi_setting('min_food_cents')::integer, 2400);
  fee := coalesce(public.pidi_setting('fee_cents')::integer, 500);
  if food < minimum then
    raise exception 'Food minimum is ƒ24 before delivery.';
  end if;

  pay := lower(trim(coalesce(payload->>'pay', '')));
  if pay = 'cash' then
    pays := (payload->>'pays_with_cents')::integer;
    if pays is null or pays < food + fee then
      raise exception 'Cash paid must cover the food and the ƒ5 delivery.';
    end if;
  elsif pay = 'transfer' then
    pays := null;
  else
    raise exception 'Pay cash or by bank transfer.';
  end if;

  if nullif(payload->>'lat', '') is not null or nullif(payload->>'lng', '') is not null then
    v_lat := (payload->>'lat')::numeric;
    v_lng := (payload->>'lng')::numeric;
    if v_lat is null or v_lng is null or v_lat < -90 or v_lat > 90 or v_lng < -180 or v_lng > 180 then
      raise exception 'The map pin is not valid.';
    end if;
  end if;

  if nullif(payload->>'due_at', '') is not null then
    v_due := (payload->>'due_at')::timestamptz;
  else
    v_due := now();
  end if;

  hours := coalesce(public.pidi_setting('hours_mode'), 'reject');
  local_time := (now() at time zone 'America/Aruba')::time;
  if not (local_time >= time '22:00' or local_time < time '02:00') then
    if hours = 'flag' then
      outside := true;
    else
      raise exception 'Orders are open from 10:00 PM to 2:00 AM.';
    end if;
  end if;

  client_token := nullif(trim(coalesce(payload->>'client_token', '')), '');
  if client_token is not null then
    select jsonb_build_object(
      'order_id', o.id,
      'public_token', o.public_token,
      'food_cents', o.food_cents,
      'fee_cents', o.fee_cents,
      'total_cents', o.food_cents + o.fee_cents,
      'change_due_cents', o.change_due_cents,
      'restaurant', rest_name
    ) into existing
    from public.pidi_orders o
    where o.client_token = client_token;
    if existing is not null then
      return existing;
    end if;
  end if;

  token := public.pidi_new_token();
  insert into public.pidi_orders (
    restaurant_id, public_token, client_token, customer_name, phone, area, address,
    lat, lng, note, pay, food_cents, fee_cents, pays_with_cents, transfer_status,
    due_at, outside_hours, test
  ) values (
    rest_id, token, client_token, uname, trim(payload->>'phone'), trim(payload->>'area'),
    trim(payload->>'address'), v_lat, v_lng, nullif(trim(coalesce(payload->>'note', '')), ''),
    pay::public.pidi_pay_method, food, fee, pays,
    case when pay = 'transfer' then 'awaiting'::public.pidi_transfer_status else null end,
    v_due, outside, coalesce(lower(payload->>'test') in ('true', '1', 'yes'), false)
  ) returning id into order_id;

  insert into public.pidi_order_items (order_id, name, qty, price_cents)
  select order_id, trim(dish->>'name'), (dish->>'qty')::integer, (dish->>'price_cents')::integer
  from jsonb_array_elements(payload->'items') dish;

  perform public.pidi_log(order_id, 'new');

  return jsonb_build_object(
    'order_id', order_id,
    'public_token', token,
    'food_cents', food,
    'fee_cents', fee,
    'total_cents', food + fee,
    'change_due_cents', case when pay = 'cash' then pays - (food + fee) else null end,
    'restaurant', rest_name
  );
end
$$;

create or replace function public.pidi_order_status(token text)
returns jsonb
language plpgsql
stable
security definer
set search_path = public, extensions
as $$
declare
  result jsonb;
begin
  select jsonb_build_object(
    'status', o.status,
    'label', case o.status
      when 'new' then 'Received'
      when 'accepted' then 'Received'
      when 'cooking' then 'Cooking'
      when 'ready' then 'Cooking'
      when 'assigned' then 'On the way'
      when 'picked_up' then 'On the way'
      when 'delivered' then 'Delivered'
      when 'cancelled' then 'Cancelled'
      else 'Received' end,
    'restaurant', r.name,
    'topic', 'pidi:order:' || o.public_token
  ) into result
  from public.pidi_orders o
  join public.pidi_restaurants r on r.id = o.restaurant_id
  where o.public_token = token;
  if result is null then
    raise exception 'We can''t find that order.';
  end if;
  return result;
end
$$;

create or replace function public.pidi_kitchen_ok(token text)
returns boolean
language plpgsql
stable
security definer
set search_path = public, extensions
as $$
declare
  ok boolean;
begin
  if token is null or length(token) < 20 then
    return false;
  end if;
  select true into ok
  from public.pidi_kitchen_sessions s
  where s.expires_at > now()
    and extensions.crypt(token, s.token_hash) = s.token_hash
  limit 1;
  return coalesce(ok, false);
end
$$;

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
  if pin is null or pin !~ '^[0-9]{4,8}$' then
    raise exception 'That PIN does not match.';
  end if;
  hash := public.pidi_setting('kitchen_pin_hash');
  if hash is null or hash = '' then
    raise exception 'The kitchen PIN is not set yet.';
  end if;
  locked := nullif(public.pidi_setting('kitchen_pin_locked_until'), '')::timestamptz;
  if locked is not null and locked > now() then
    raise exception 'Too many tries. Wait 5 minutes.';
  end if;
  if extensions.crypt(pin, hash) is distinct from hash then
    failures := coalesce(public.pidi_setting('kitchen_pin_failures')::integer, 0) + 1;
    insert into public.pidi_settings (key, value) values ('kitchen_pin_failures', failures::text)
    on conflict (key) do update set value = excluded.value;
    if failures >= 5 then
      insert into public.pidi_settings (key, value)
      values ('kitchen_pin_locked_until', (now() + interval '5 minutes')::text)
      on conflict (key) do update set value = excluded.value;
    end if;
    raise exception 'That PIN does not match.';
  end if;
  insert into public.pidi_settings (key, value) values ('kitchen_pin_failures', '0')
  on conflict (key) do update set value = '0';
  delete from public.pidi_settings where key = 'kitchen_pin_locked_until';
  delete from public.pidi_kitchen_sessions where expires_at < now() - interval '1 day';
  token := public.pidi_new_token();
  hours := coalesce(public.pidi_setting('session_hours')::integer, 12);
  insert into public.pidi_kitchen_sessions (token_hash, expires_at)
  values (extensions.crypt(token, extensions.gen_salt('bf', 8)), now() + make_interval(hours => hours));
  return jsonb_build_object(
    'token', token,
    'expires_at', now() + make_interval(hours => hours),
    'topic', public.pidi_kitchen_topic()
  );
end
$$;

create or replace function public.pidi_kitchen_feed(session text)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
begin
  if not public.pidi_kitchen_ok(session) then
    raise exception 'Sign in again.';
  end if;
  return jsonb_build_object(
    'topic', public.pidi_kitchen_topic(),
    'orders', coalesce((
      select jsonb_agg(row_to_json(x) order by x.created_at)
      from (
        select o.id, o.status, r.name as restaurant, o.customer_name as name, o.phone,
               o.area, o.address, o.note, o.pay, o.food_cents, o.fee_cents,
               o.food_cents + o.fee_cents as total_cents, o.pays_with_cents, o.change_due_cents,
               o.transfer_status, o.outside_hours, o.test, o.created_at,
               (
                 select coalesce(jsonb_agg(jsonb_build_object('name', i.name, 'qty', i.qty, 'price_cents', i.price_cents)), '[]'::jsonb)
                 from public.pidi_order_items i where i.order_id = o.id
               ) as items
        from public.pidi_orders o
        join public.pidi_restaurants r on r.id = o.restaurant_id
        where o.status not in ('delivered', 'cancelled')
      ) x
    ), '[]'::jsonb)
  );
end
$$;

create or replace function public.pidi_kitchen_move(session text, order_id uuid, next_status text)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  cur text;
  when_status text;
begin
  if not public.pidi_kitchen_ok(session) then
    raise exception 'Sign in again.';
  end if;
  if next_status in ('delivered', 'assigned', 'picked_up', 'cancelled') then
    raise exception 'The kitchen stops at Ready. The driver marks picked up and delivered.';
  end if;
  select status::text into cur from public.pidi_orders where id = order_id for update;
  if not found then
    raise exception 'No such order.';
  end if;
  if not (
    (next_status = 'accepted' and cur = 'new')
    or (next_status = 'cooking' and cur = 'accepted')
    or (next_status = 'ready' and cur = 'cooking')
  ) then
    raise exception 'Move one step at a time.';
  end if;
  update public.pidi_orders set status = next_status::public.pidi_status where id = order_id;
  perform public.pidi_log(order_id, next_status);
  when_status := coalesce(public.pidi_setting('dispatch_when'), 'ready');
  if (next_status = 'ready' and when_status = 'ready')
     or (next_status = 'accepted' and when_status = 'accepted') then
    perform public.pidi_dispatch();
  end if;
  return jsonb_build_object('ok', true, 'status', next_status);
end
$$;

create or replace function public.pidi_kitchen_accept(session text, order_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
begin
  return public.pidi_kitchen_move(session, order_id, 'accepted');
end
$$;

create or replace function public.pidi_kitchen_set_status(session text, order_id uuid, status text)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
begin
  return public.pidi_kitchen_move(session, order_id, status);
end
$$;

create or replace function public.pidi_driver_id(token text)
returns uuid
language plpgsql
stable
security definer
set search_path = public, extensions
as $$
declare
  found_id uuid;
begin
  if token is null or length(token) < 20 then
    raise exception 'Sign in again.';
  end if;
  select s.driver_id into found_id
  from public.pidi_driver_sessions s
  where s.expires_at > now()
    and extensions.crypt(token, s.token_hash) = s.token_hash
  limit 1;
  if found_id is null then
    raise exception 'Sign in again.';
  end if;
  return found_id;
end
$$;

-- Returns null when the PIN is good. A wrong PIN is returned as text, not raised:
-- a raised error would roll the failure count back, and the lock would never stick.
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
  delete from public.pidi_settings where key = 'admin_pin_locked_until';
  return null;
end
$$;

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
  if new_pin is null or new_pin !~ '^[0-9]{4,8}$' then
    raise exception 'Kitchen PIN must be 4 to 8 digits.';
  end if;
  insert into public.pidi_settings (key, value)
  values ('kitchen_pin_hash', extensions.crypt(new_pin, extensions.gen_salt('bf', 8)))
  on conflict (key) do update set value = excluded.value;
  insert into public.pidi_settings (key, value) values ('kitchen_pin_failures', '0')
  on conflict (key) do update set value = '0';
  delete from public.pidi_settings where key = 'kitchen_pin_locked_until';
  delete from public.pidi_kitchen_sessions;
  return '{"ok":true}'::jsonb;
end
$$;

create or replace function public.pidi_admin_add_driver(admin_pin text, name text, phone text, pin text)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  driver uuid;
  driver_code text;
  admin_msg text;
begin
  admin_msg := public.pidi_admin_ok(admin_pin);
  if admin_msg is not null then
    return jsonb_build_object('ok', false, 'error', admin_msg);
  end if;
  if name is null or length(trim(name)) < 2 then
    raise exception 'Enter the driver''s name.';
  end if;
  if pin is null or pin !~ '^[0-9]{4,8}$' then
    raise exception 'Driver PIN must be 4 to 8 digits.';
  end if;
  driver_code := lower(regexp_replace(trim(name), '\s+', '', 'g'));
  insert into public.pidi_drivers (name, phone, code, pin_hash)
  values (trim(name), nullif(trim(coalesce(phone, '')), ''), driver_code, extensions.crypt(pin, extensions.gen_salt('bf', 8)))
  returning id into driver;
  return jsonb_build_object('ok', true, 'driver_id', driver, 'code', driver_code);
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
  select * into drv
  from public.pidi_drivers d
  where d.active and (d.code = key or lower(d.name) = key or d.id::text = key);
  if not found then
    raise exception 'That PIN does not match.';
  end if;
  if drv.pin_locked_until is not null and drv.pin_locked_until > now() then
    raise exception 'Too many tries. Wait 5 minutes.';
  end if;
  if pin is null or pin !~ '^[0-9]{4,8}$'
     or extensions.crypt(pin, drv.pin_hash) is distinct from drv.pin_hash then
    update public.pidi_drivers
      set pin_failures = pin_failures + 1,
          pin_locked_until = case when pin_failures + 1 >= 5 then now() + interval '5 minutes' else pin_locked_until end
      where id = drv.id;
    raise exception 'That PIN does not match.';
  end if;
  update public.pidi_drivers
    set pin_failures = 0, pin_locked_until = null
    where id = drv.id;
  delete from public.pidi_driver_sessions
    where driver_id = drv.id and expires_at < now() - interval '1 day';
  token := public.pidi_new_token();
  hours := coalesce(public.pidi_setting('session_hours')::integer, 12);
  insert into public.pidi_driver_sessions (driver_id, token_hash, expires_at)
  values (drv.id, extensions.crypt(token, extensions.gen_salt('bf', 8)), now() + make_interval(hours => hours));
  return jsonb_build_object(
    'token', token,
    'driver_id', drv.id,
    'name', drv.name,
    'topic', 'pidi:driver:' || drv.id::text,
    'expires_at', now() + make_interval(hours => hours)
  );
end
$$;

create or replace function public.pidi_driver_set_online(session text, online boolean)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  drv uuid;
begin
  drv := public.pidi_driver_id(session);
  update public.pidi_drivers as d
    set online = coalesce(pidi_driver_set_online.online, false)
    where d.id = drv;
  if coalesce(pidi_driver_set_online.online, false) then
    perform public.pidi_dispatch();
  end if;
  return jsonb_build_object('ok', true, 'online', coalesce(pidi_driver_set_online.online, false));
end
$$;

create or replace function public.pidi_driver_offers(session text)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  drv uuid;
begin
  drv := public.pidi_driver_id(session);
  perform public.pidi_dispatch();
  return coalesce((
    select jsonb_agg(offer order by offer->>'expires_at')
    from (
      select jsonb_build_object(
        'offer_id', f.id,
        'run_id', f.run_id,
        'seconds_left', greatest(0, ceil(extract(epoch from (f.expires_at - now())))::integer),
        'stops', (
          select coalesce(jsonb_agg(jsonb_build_object(
            'stop_index', ro.stop_index,
            'restaurant', r.name,
            'name', o.customer_name,
            'area', o.area,
            'pay', o.pay,
            'total_cents', o.food_cents + o.fee_cents
          ) order by ro.stop_index), '[]'::jsonb)
          from public.pidi_run_orders ro
          join public.pidi_orders o on o.id = ro.order_id
          join public.pidi_restaurants r on r.id = o.restaurant_id
          where ro.run_id = f.run_id
        )
      ) as offer
      from public.pidi_offers f
      where f.driver_id = drv and f.status = 'pending' and f.expires_at > now()
    ) s
  ), '[]'::jsonb);
end
$$;

create or replace function public.pidi_driver_accept(session text, offer_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  drv uuid;
  v_run uuid;
  v_offer_driver uuid;
  v_offer_status text;
  v_expires timestamptz;
  v_run_status text;
begin
  drv := public.pidi_driver_id(session);
  select run_id, driver_id, status::text, expires_at
    into v_run, v_offer_driver, v_offer_status, v_expires
  from public.pidi_offers
  where id = offer_id;
  if not found or v_offer_driver is distinct from drv then
    raise exception 'That offer is not yours.';
  end if;
  select status::text into v_run_status from public.pidi_runs where id = v_run for update;
  select status::text, expires_at into v_offer_status, v_expires
  from public.pidi_offers where id = offer_id for update;
  if v_offer_status = 'expired' or v_expires <= now() then
    update public.pidi_offers set status = 'expired' where id = offer_id and status = 'pending';
    raise exception 'That offer expired.';
  end if;
  if v_offer_status = 'lost' or v_run_status = 'active' then
    raise exception 'Another driver took this run.';
  end if;
  if v_offer_status <> 'pending' or v_run_status <> 'offered' then
    raise exception 'That offer is not open.';
  end if;
  update public.pidi_runs
    set status = 'active', driver_id = drv
    where id = v_run and status = 'offered';
  if not found then
    raise exception 'Another driver took this run.';
  end if;
  update public.pidi_offers set status = 'accepted' where id = offer_id;
  update public.pidi_offers set status = 'lost'
    where run_id = v_run and id <> offer_id and status = 'pending';
  update public.pidi_orders o
    set status = 'assigned'
    from public.pidi_run_orders ro
    where ro.run_id = v_run and ro.order_id = o.id and o.status in ('accepted', 'cooking', 'ready');
  insert into public.pidi_order_events (order_id, status)
  select ro.order_id, 'assigned'
  from public.pidi_run_orders ro
  where ro.run_id = v_run;
  return jsonb_build_object('ok', true, 'run_id', v_run);
end
$$;

create or replace function public.pidi_driver_decline(session text, offer_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  drv uuid;
begin
  drv := public.pidi_driver_id(session);
  update public.pidi_offers
    set status = 'declined'
    where id = offer_id and driver_id = drv and status = 'pending';
  if not found then
    raise exception 'That offer is not yours.';
  end if;
  return '{"ok":true}'::jsonb;
end
$$;

create or replace function public.pidi_driver_run(session text)
returns jsonb
language plpgsql
stable
security definer
set search_path = public, extensions
as $$
declare
  drv uuid;
  result jsonb;
begin
  drv := public.pidi_driver_id(session);
  select jsonb_build_object(
    'run_id', r.id,
    'pickup', jsonb_build_object(
      'name', coalesce(public.pidi_setting('pickup_name'), ''),
      'address', coalesce(public.pidi_setting('pickup_address'), ''),
      'lat', nullif(public.pidi_setting('pickup_lat'), ''),
      'lng', nullif(public.pidi_setting('pickup_lng'), '')
    ),
    'stops', (
      select coalesce(jsonb_agg(jsonb_build_object(
        'order_id', o.id,
        'stop_index', ro.stop_index,
        'status', o.status,
        'restaurant', rest.name,
        'name', o.customer_name,
        'phone', o.phone,
        'area', o.area,
        'address', o.address,
        'lat', o.lat,
        'lng', o.lng,
        'note', o.note,
        'pay', o.pay,
        'total_cents', o.food_cents + o.fee_cents,
        'pays_with_cents', o.pays_with_cents,
        'change_due_cents', o.change_due_cents,
        'transfer_status', o.transfer_status,
        'items', (
          select coalesce(jsonb_agg(jsonb_build_object('name', i.name, 'qty', i.qty)), '[]'::jsonb)
          from public.pidi_order_items i where i.order_id = o.id
        )
      ) order by ro.stop_index), '[]'::jsonb)
      from public.pidi_run_orders ro
      join public.pidi_orders o on o.id = ro.order_id
      join public.pidi_restaurants rest on rest.id = o.restaurant_id
      where ro.run_id = r.id
    )
  ) into result
  from public.pidi_runs r
  where r.driver_id = drv and r.status = 'active'
  order by r.created_at desc
  limit 1;
  return result;
end
$$;

create or replace function public.pidi_driver_picked_up(session text, run_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  drv uuid;
begin
  drv := public.pidi_driver_id(session);
  if not exists (select 1 from public.pidi_runs r where r.id = pidi_driver_picked_up.run_id and r.driver_id = drv and r.status = 'active') then
    raise exception 'That run is not yours.';
  end if;
  update public.pidi_orders o
    set status = 'picked_up'
    from public.pidi_run_orders ro
    where ro.run_id = pidi_driver_picked_up.run_id and ro.order_id = o.id and o.status = 'assigned';
  insert into public.pidi_order_events (order_id, status)
  select ro.order_id, 'picked_up'
  from public.pidi_run_orders ro
  join public.pidi_orders o on o.id = ro.order_id
  where ro.run_id = pidi_driver_picked_up.run_id and o.status = 'picked_up'
    and not exists (
      select 1 from public.pidi_order_events e
      where e.order_id = o.id and e.status = 'picked_up'
    );
  return '{"ok":true}'::jsonb;
end
$$;

create or replace function public.pidi_driver_delivered(session text, order_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  drv uuid;
  v_run uuid;
begin
  drv := public.pidi_driver_id(session);
  select r.id into v_run
  from public.pidi_runs r
  join public.pidi_run_orders ro on ro.run_id = r.id
  where ro.order_id = pidi_driver_delivered.order_id and r.driver_id = drv and r.status = 'active';
  if v_run is null then
    raise exception 'That run is not yours.';
  end if;
  update public.pidi_orders
    set status = 'delivered'
    where id = pidi_driver_delivered.order_id and status = 'picked_up';
  if not found then
    raise exception 'Pick up the bags before you mark this delivered.';
  end if;
  perform public.pidi_log(pidi_driver_delivered.order_id, 'delivered');
  if not exists (
    select 1
    from public.pidi_run_orders ro
    join public.pidi_orders o on o.id = ro.order_id
    where ro.run_id = v_run and o.status <> 'delivered'
  ) then
    update public.pidi_runs set status = 'done' where id = v_run;
  end if;
  return '{"ok":true}'::jsonb;
end
$$;

create or replace function public.pidi_driver_location(session text, lat numeric, lng numeric)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  drv uuid;
  gap integer;
  last_at timestamptz;
begin
  drv := public.pidi_driver_id(session);
  if lat is null or lng is null or lat < -90 or lat > 90 or lng < -180 or lng > 180 then
    raise exception 'The map pin is not valid.';
  end if;
  if not exists (select 1 from public.pidi_runs r where r.driver_id = drv and r.status = 'active') then
    raise exception 'Location is only sent during a run.';
  end if;
  gap := coalesce(public.pidi_setting('location_seconds')::integer, 8);
  select at into last_at from public.pidi_driver_locations where driver_id = drv;
  if last_at is not null and last_at > now() - make_interval(secs => gap) then
    return jsonb_build_object('ok', true, 'skipped', true);
  end if;
  insert into public.pidi_driver_locations (driver_id, lat, lng, at)
  values (drv, pidi_driver_location.lat, pidi_driver_location.lng, now())
  on conflict (driver_id) do update set lat = excluded.lat, lng = excluded.lng, at = excluded.at;
  perform public.pidi_broadcast('pidi:driver:' || drv::text);
  return jsonb_build_object('ok', true, 'skipped', false);
end
$$;

create or replace function public.pidi_trg_order_ping()
returns trigger
language plpgsql
security definer
set search_path = public, extensions
as $$
begin
  perform public.pidi_broadcast(public.pidi_kitchen_topic());
  perform public.pidi_broadcast('pidi:order:' || new.public_token);
  return null;
end
$$;

create or replace function public.pidi_trg_offer_ping()
returns trigger
language plpgsql
security definer
set search_path = public, extensions
as $$
begin
  perform public.pidi_broadcast('pidi:driver:' || new.driver_id::text);
  return null;
end
$$;

drop trigger if exists pidi_trg_orders_ping on public.pidi_orders;
create trigger pidi_trg_orders_ping
  after insert or update on public.pidi_orders
  for each row execute function public.pidi_trg_order_ping();

drop trigger if exists pidi_trg_offers_ping on public.pidi_offers;
create trigger pidi_trg_offers_ping
  after insert or update on public.pidi_offers
  for each row execute function public.pidi_trg_offer_ping();

alter table public.pidi_restaurants enable row level security;
alter table public.pidi_settings enable row level security;
alter table public.pidi_drivers enable row level security;
alter table public.pidi_orders enable row level security;
alter table public.pidi_order_items enable row level security;
alter table public.pidi_order_events enable row level security;
alter table public.pidi_runs enable row level security;
alter table public.pidi_run_orders enable row level security;
alter table public.pidi_offers enable row level security;
alter table public.pidi_driver_locations enable row level security;
alter table public.pidi_kitchen_sessions enable row level security;
alter table public.pidi_driver_sessions enable row level security;

alter table public.pidi_orders replica identity full;
alter table public.pidi_runs replica identity full;
alter table public.pidi_offers replica identity full;
alter table public.pidi_driver_locations replica identity full;

do $pidi_rls$
declare
  t text;
begin
  foreach t in array array[
    'pidi_restaurants', 'pidi_settings', 'pidi_drivers', 'pidi_orders', 'pidi_order_items',
    'pidi_order_events', 'pidi_runs', 'pidi_run_orders', 'pidi_offers',
    'pidi_driver_locations', 'pidi_kitchen_sessions', 'pidi_driver_sessions'
  ]
  loop
    execute format('drop policy if exists %I on public.%I', t || '_no_select', t);
    execute format(
      'create policy %I on public.%I for all to anon using (false) with check (false)',
      t || '_no_select', t
    );
  end loop;
end
$pidi_rls$;

do $pidi_grants$
declare
  sig text;
begin
  for sig in
    select p.oid::regprocedure::text
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public' and p.proname like 'pidi\_%' escape '\'
  loop
    execute format('revoke all on function %s from public', sig);
  end loop;
end
$pidi_grants$;

grant execute on function public.pidi_ping() to anon;
grant execute on function public.pidi_place_order(jsonb) to anon;
grant execute on function public.pidi_order_status(text) to anon;
grant execute on function public.pidi_kitchen_login(text) to anon;
grant execute on function public.pidi_kitchen_feed(text) to anon;
grant execute on function public.pidi_kitchen_accept(text, uuid) to anon;
grant execute on function public.pidi_kitchen_set_status(text, uuid, text) to anon;
grant execute on function public.pidi_driver_login(text, text) to anon;
grant execute on function public.pidi_driver_set_online(text, boolean) to anon;
grant execute on function public.pidi_driver_offers(text) to anon;
grant execute on function public.pidi_driver_accept(text, uuid) to anon;
grant execute on function public.pidi_driver_decline(text, uuid) to anon;
grant execute on function public.pidi_driver_run(text) to anon;
grant execute on function public.pidi_driver_picked_up(text, uuid) to anon;
grant execute on function public.pidi_driver_delivered(text, uuid) to anon;
grant execute on function public.pidi_driver_location(text, numeric, numeric) to anon;
grant execute on function public.pidi_admin_add_driver(text, text, text, text) to anon;
grant execute on function public.pidi_admin_set_kitchen_pin(text, text) to anon;

do $pidi_pub$
declare
  t text;
begin
  if not exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    raise notice 'supabase_realtime is not on this server. Skipped. Hosted Supabase already has it.';
    return;
  end if;
  foreach t in array array['pidi_orders', 'pidi_runs', 'pidi_offers', 'pidi_driver_locations']
  loop
    if to_regclass('public.' || t) is not null and not exists (
      select 1 from pg_publication_tables
      where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = t
    ) then
      execute format('alter publication supabase_realtime add table public.%I', t);
    end if;
  end loop;
end
$pidi_pub$;

-- ---------------------------------------------------------------------------
-- Seed, run by hand after the paste. Edit the PINs. Do not commit real PINs.
-- The dashboard runs this as the database owner, not as a customer.
-- The admin PIN is exactly 8 digits. Kitchen and driver PINs are 4 to 8 digits.
-- Five wrong admin PINs lock admin checks for 5 minutes.
--
-- insert into public.pidi_settings (key, value)
-- values ('admin_pin_hash', extensions.crypt('PUT_8_DIGIT_ADMIN_PIN', extensions.gen_salt('bf', 8)))
-- on conflict (key) do nothing;
--
-- select public.pidi_admin_set_kitchen_pin('PUT_8_DIGIT_ADMIN_PIN', 'PUT_KITCHEN_PIN');
-- select public.pidi_admin_add_driver('PUT_8_DIGIT_ADMIN_PIN', 'Ari', '2975550000', 'PUT_DRIVER_PIN');
--
-- A daytime test, until you set it back to reject:
-- update public.pidi_settings set value = 'flag' where key = 'hours_mode';
-- ---------------------------------------------------------------------------
