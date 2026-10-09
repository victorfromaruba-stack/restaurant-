-- Pidi v2. One order row, the kitchen sees it, a free driver is offered the run.
-- Apply in the Supabase SQL editor, or with `supabase db push` from driver/v2.
-- No secrets in this file. PINs are hashed later by the owner (see README).

create schema if not exists extensions;
do $$
begin
  if not exists (select 1 from pg_extension where extname = 'pgcrypto') then
    create extension pgcrypto with schema extensions;
  end if;
end $$;

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then
    create role anon nologin noinherit;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then
    create role authenticated nologin noinherit;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'service_role') then
    create role service_role nologin noinherit bypassrls;
  end if;
end $$;

create schema if not exists auth;
do $$
begin
  if not exists (
    select 1 from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'auth' and p.proname = 'jwt'
  ) then
    create function auth.jwt() returns jsonb
    language sql stable
    as $fn$
      select coalesce(nullif(current_setting('request.jwt.claims', true), ''), '{}')::jsonb
    $fn$;
  end if;
end $$;

grant usage on schema auth to anon, authenticated, service_role;
grant execute on function auth.jwt() to anon, authenticated, service_role;
grant usage on schema public to anon, authenticated, service_role;
grant usage on schema extensions to anon, authenticated, service_role;

-- Private functions. Not added to the Data API schemas.
create schema if not exists pidi;
revoke all on schema pidi from public;
grant usage on schema pidi to anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------

create type public.order_status as enum (
  'new', 'accepted', 'cooking', 'ready', 'assigned', 'picked_up', 'delivered', 'cancelled'
);
create type public.pay_method as enum ('cash', 'transfer');
create type public.transfer_status as enum ('awaiting', 'paid');
create type public.run_status as enum ('offered', 'active', 'done', 'cancelled');
create type public.offer_status as enum ('pending', 'accepted', 'declined', 'expired', 'lost');

create table public.restaurants (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  name text not null,
  partner boolean not null default false,
  active boolean not null default true,
  created_at timestamptz not null default now()
);

create table public.staff (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  code text not null unique,
  pin_hash text not null,
  active boolean not null default true,
  pin_failures int not null default 0,
  pin_locked_until timestamptz,
  created_at timestamptz not null default now()
);

create table public.drivers (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  code text not null unique,
  pin_hash text not null,
  active boolean not null default true,
  online boolean not null default false,
  pin_failures int not null default 0,
  pin_locked_until timestamptz,
  created_at timestamptz not null default now()
);

create table public.settings (
  key text primary key,
  value text not null,
  is_public boolean not null default false
);

create function public.pidi_token() returns text
language sql volatile
set search_path = public, extensions
as $$ select encode(gen_random_bytes(24), 'hex') $$;

create table public.orders (
  id uuid primary key default gen_random_uuid(),
  public_token text not null unique default public.pidi_token(),
  client_token text unique,
  ref text not null unique,
  restaurant_id uuid not null references public.restaurants (id),
  status public.order_status not null default 'new',
  customer_name text not null,
  phone text not null,
  area text not null default '',
  address text not null,
  lat double precision,
  lng double precision,
  note text not null default '',
  pay_method public.pay_method not null,
  pays_with_cents int,
  transfer_status public.transfer_status,
  food_cents int not null,
  fee_cents int not null default 500,
  total_cents int generated always as (food_cents + fee_cents) stored,
  change_due_cents int generated always as (
    case
      when pay_method = 'cash' and pays_with_cents is not null
        then pays_with_cents - (food_cents + fee_cents)
      else null
    end
  ) stored,
  outside_hours boolean not null default false,
  due_at timestamptz not null default now(),
  test boolean not null default false,
  checkout_id uuid,
  created_at timestamptz not null default now(),
  -- ƒ24 is checked on the whole checkout in place_order / place_checkout.
  -- A second restaurant in the same checkout can be under ƒ24 on its own.
  constraint orders_food_nonneg check (food_cents >= 0),
  constraint orders_fee_exact check (fee_cents in (0, 500)),
  constraint orders_pay_shape check (
    (
      pay_method = 'cash' and transfer_status is null and (
        (fee_cents = 500 and pays_with_cents is not null and pays_with_cents >= 0)
        or (fee_cents = 0 and pays_with_cents is null)
      )
    )
    or
    (
      pay_method = 'transfer' and pays_with_cents is null and (
        (fee_cents = 500 and transfer_status is not null)
        or (fee_cents = 0 and transfer_status is null)
      )
    )
  ),
  constraint orders_pin_pair check (
    (lat is null and lng is null) or (lat is not null and lng is not null)
  )
);

create table public.order_items (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.orders (id) on delete cascade,
  name text not null,
  qty int not null check (qty > 0 and qty <= 12),
  price_cents int not null check (price_cents >= 0 and price_cents < 1000000)
);

create table public.order_events (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.orders (id) on delete cascade,
  status public.order_status not null,
  actor text not null,
  created_at timestamptz not null default now()
);

create table public.runs (
  id uuid primary key default gen_random_uuid(),
  driver_id uuid references public.drivers (id),
  status public.run_status not null default 'offered',
  step text not null default 'pickup' check (step in ('pickup', 'drop', 'done')),
  drop_index int not null default 0 check (drop_index >= 0 and drop_index < 2),
  created_at timestamptz not null default now(),
  accepted_at timestamptz,
  finished_at timestamptz
);

-- An order sits on at most one live run. stop_index 1 and 2 cap a run at two orders.
create table public.run_orders (
  run_id uuid not null references public.runs (id) on delete cascade,
  order_id uuid not null references public.orders (id),
  stop_index int not null check (stop_index in (1, 2)),
  primary key (run_id, order_id),
  unique (run_id, stop_index)
);

create unique index run_orders_one_live_order on public.run_orders (order_id);

create table public.offers (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.runs (id) on delete cascade,
  driver_id uuid not null references public.drivers (id),
  status public.offer_status not null default 'pending',
  expires_at timestamptz not null,
  created_at timestamptz not null default now()
);

create unique index offers_one_pending on public.offers (run_id, driver_id)
  where status = 'pending';

create table public.driver_locations (
  driver_id uuid primary key references public.drivers (id),
  run_id uuid references public.runs (id),
  lat double precision not null,
  lng double precision not null,
  recorded_at timestamptz not null default now()
);

create index orders_open_due on public.orders (status, due_at);
create index offers_driver_pending on public.offers (driver_id) where status = 'pending';
create index runs_driver_active on public.runs (driver_id) where status = 'active';
create index order_items_order on public.order_items (order_id);
create index order_events_order on public.order_events (order_id, created_at);

insert into public.restaurants (slug, name, partner) values
  ('dushi-wok', 'Dushi Wok', false),
  ('taco-brava', 'Taco Brava', false),
  ('smash-shack', 'Smash Shack', false),
  ('nonnas-night-in', 'Nonna''s Night In', false),
  ('oranje-snack', 'Oranje Snack', false);

insert into public.settings (key, value, is_public) values
  ('dispatch_when', 'ready', false),
  ('offer_seconds', '45', false),
  ('pair_minutes', '10', false),
  ('pair_km', '3', false),
  ('fee_cents', '500', true),
  ('min_food_cents', '2400', true),
  ('hours_mode', 'reject', true),
  ('pickup_name', '', false),
  ('pickup_address', '', false),
  ('pickup_lat', '', false),
  ('pickup_lng', '', false);

-- ---------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------

create function pidi.setting(k text) returns text
language sql stable
set search_path = ''
as $$ select value from public.settings where key = k $$;

create function pidi.within_hours(ts timestamptz) returns boolean
language sql stable
set search_path = ''
as $$
  select (ts at time zone 'America/Aruba')::time >= time '22:00'
      or (ts at time zone 'America/Aruba')::time < time '02:00'
$$;

-- Haversine, kilometres. Used only to pair two drops.
create function pidi.km(lat1 float8, lng1 float8, lat2 float8, lng2 float8) returns float8
language sql immutable
set search_path = ''
as $$
  select 6371 * 2 * asin(sqrt(
    power(sin(radians(lat2 - lat1) / 2), 2)
    + cos(radians(lat1)) * cos(radians(lat2)) * power(sin(radians(lng2 - lng1) / 2), 2)
  ))
$$;

create function pidi.hash_pin(pin text) returns text
language sql volatile
set search_path = public, extensions
as $$ select crypt(pin, gen_salt('bf', 8)) $$;

create function pidi.pin_ok(pin text, pin_hash text) returns boolean
language sql stable
set search_path = public, extensions
as $$ select pin_hash is not null and crypt(pin, pin_hash) = pin_hash $$;

create function pidi.clock() returns timestamptz
language sql stable
set search_path = ''
as $$
  select coalesce(nullif(current_setting('pidi.now', true), '')::timestamptz, now())
$$;

create function pidi.driver_id() returns uuid
language sql stable
set search_path = ''
as $$ select nullif(auth.jwt() ->> 'driver_id', '')::uuid $$;

create function pidi.is_kitchen() returns boolean
language sql stable
set search_path = ''
as $$ select (auth.jwt() ->> 'staff_role') = 'kitchen' $$;

create function pidi.make_ref() returns text
language plpgsql volatile
set search_path = ''
as $$
declare
  candidate text;
  n int := 0;
begin
  loop
    n := n + 1;
    candidate := to_char(pidi.clock() at time zone 'America/Aruba', 'HH24MI')
      || '-'
      || chr(65 + floor(random() * 26)::int)
      || chr(65 + floor(random() * 26)::int);
    exit when not exists (select 1 from public.orders where ref = candidate);
    if n > 20 then
      raise exception 'Could not make an order number';
    end if;
  end loop;
  return candidate;
end;
$$;

-- ---------------------------------------------------------------------------
-- Status rules
-- ---------------------------------------------------------------------------

create function pidi.driver_has_order(order_id uuid) returns boolean
language sql stable
set search_path = ''
as $$
  select exists (
    select 1
    from public.run_orders ro
    join public.runs r on r.id = ro.run_id
    where ro.order_id = driver_has_order.order_id
      and r.driver_id = pidi.driver_id()
      and r.status = 'active'
  )
$$;

create function pidi.assert_status(
  old_status public.order_status,
  new_status public.order_status,
  actor text,
  order_id uuid
) returns void
language plpgsql
set search_path = ''
as $$
begin
  if old_status = new_status then
    return;
  end if;
  if actor = 'dispatch' and old_status in ('accepted', 'cooking', 'ready') and new_status = 'assigned' then
    return;
  end if;
  if actor = 'kitchen' and old_status = 'new' and new_status in ('accepted', 'cancelled') then
    return;
  end if;
  if actor = 'kitchen' and old_status = 'accepted' and new_status in ('cooking', 'cancelled') then
    return;
  end if;
  if actor = 'kitchen' and old_status = 'cooking' and new_status in ('ready', 'cancelled') then
    return;
  end if;
  if actor = 'kitchen' and old_status = 'ready' and new_status = 'cancelled' then
    return;
  end if;
  if actor = 'driver' and old_status = 'assigned' and new_status = 'picked_up' and pidi.driver_has_order(order_id) then
    return;
  end if;
  if actor = 'driver' and old_status = 'picked_up' and new_status = 'delivered' and pidi.driver_has_order(order_id) then
    return;
  end if;
  raise exception 'Cannot move an order from % to %', old_status, new_status;
end;
$$;

create function pidi.guard_order() returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  actor text := nullif(current_setting('pidi.actor', true), '');
  moment timestamptz;
  mode text;
begin
  if tg_op = 'INSERT' then
    moment := pidi.clock();
    mode := coalesce(pidi.setting('hours_mode'), 'reject');
    if current_setting('pidi.allow_anytime', true) = 'on' then
      new.outside_hours := false;
    elsif not pidi.within_hours(moment) then
      if mode = 'flag' then
        new.outside_hours := true;
      else
        raise exception 'Orders are open from 10 PM to 2 AM';
      end if;
    end if;
    if new.status <> 'new' then
      raise exception 'A new order starts as new';
    end if;
    return new;
  end if;

  if new.food_cents is distinct from old.food_cents
     or new.fee_cents is distinct from old.fee_cents
     or new.public_token is distinct from old.public_token
     or new.client_token is distinct from old.client_token
     or new.ref is distinct from old.ref
     or new.restaurant_id is distinct from old.restaurant_id
     or new.customer_name is distinct from old.customer_name
     or new.phone is distinct from old.phone
     or new.area is distinct from old.area
     or new.address is distinct from old.address
     or new.lat is distinct from old.lat
     or new.lng is distinct from old.lng
     or new.note is distinct from old.note
     or new.pay_method is distinct from old.pay_method
     or new.pays_with_cents is distinct from old.pays_with_cents
     or new.due_at is distinct from old.due_at
     or new.test is distinct from old.test
     or new.created_at is distinct from old.created_at
     or new.outside_hours is distinct from old.outside_hours
     or new.checkout_id is distinct from old.checkout_id
  then
    raise exception 'These order fields are locked';
  end if;

  if actor is null then
    if pidi.is_kitchen() then
      actor := 'kitchen';
    elsif pidi.driver_id() is not null then
      actor := 'driver';
    else
      actor := 'stranger';
    end if;
  end if;

  if new.transfer_status is distinct from old.transfer_status and actor <> 'kitchen' then
    raise exception 'Only the kitchen marks a transfer paid';
  end if;

  if new.status is distinct from old.status then
    perform pidi.assert_status(old.status, new.status, actor, old.id);
  end if;
  return new;
end;
$$;

create trigger orders_guard
  before insert or update on public.orders
  for each row execute function pidi.guard_order();

create function pidi.log_status() returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if tg_op = 'INSERT' or new.status is distinct from old.status then
    insert into public.order_events (order_id, status, actor)
    values (
      new.id,
      new.status,
      coalesce(nullif(current_setting('pidi.actor', true), ''), case when tg_op = 'INSERT' then 'customer' else 'staff' end)
    );
  end if;
  return new;
end;
$$;

create trigger orders_log
  after insert or update of status on public.orders
  for each row execute function pidi.log_status();

-- ---------------------------------------------------------------------------
-- Place an order (customer)
-- ---------------------------------------------------------------------------

create function pidi.place_order(payload jsonb) returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  rest_slug text := payload ->> 'restaurant';
  rest public.restaurants%rowtype;
  item jsonb;
  food int := 0;
  qty int;
  price int;
  pay text := payload ->> 'pay';
  pays int;
  fee int;
  checkout uuid;
  row public.orders%rowtype;
  existing public.orders%rowtype;
  token text := nullif(payload ->> 'client_token', '');
  due timestamptz;
begin
  if token is not null then
    select * into existing from public.orders where client_token = token;
    if found then
      return pidi.order_public(existing.id);
    end if;
  end if;

  select * into rest from public.restaurants where restaurants.slug = rest_slug and active;
  if not found then
    raise exception 'Unknown restaurant';
  end if;
  if coalesce(payload ->> 'name', '') = '' or coalesce(payload ->> 'address', '') = '' then
    raise exception 'Name and address are required';
  end if;
  if length(regexp_replace(coalesce(payload ->> 'phone', ''), '\D', '', 'g')) < 7 then
    raise exception 'Phone number is too short';
  end if;
  if jsonb_typeof(payload -> 'items') <> 'array' or jsonb_array_length(payload -> 'items') < 1 then
    raise exception 'Add at least one dish';
  end if;

  for item in select value from jsonb_array_elements(payload -> 'items')
  loop
    qty := (item ->> 'qty')::int;
    price := (item ->> 'price_cents')::int;
    if coalesce(item ->> 'name', '') = '' or qty is null or price is null then
      raise exception 'Each dish needs a name, a quantity and a price';
    end if;
    food := food + qty * price;
  end loop;

  if pay = 'cash' then
    pays := (payload ->> 'pays_with_cents')::int;
  elsif pay = 'transfer' then
    pays := null;
  else
    raise exception 'Payment is cash or bank transfer';
  end if;

  if (payload ? 'lat') <> (payload ? 'lng') then
    raise exception 'A pin needs both latitude and longitude';
  end if;

  due := coalesce(nullif(payload ->> 'due_at', '')::timestamptz, pidi.clock());
  if current_setting('pidi.checkout', true) = 'on' then
    fee := coalesce((payload ->> 'fee_cents')::int, 500);
    checkout := nullif(payload ->> 'checkout_id', '')::uuid;
  else
    fee := 500;
    checkout := null;
    if food < 2400 then
      raise exception 'The food minimum is ƒ24 before the delivery fee';
    end if;
  end if;
  if fee not in (0, 500) then
    raise exception 'Delivery is ƒ5';
  end if;
  if pay = 'cash' and fee = 0 then
    pays := null;
  end if;
  if pay = 'cash' and fee = 500 and pays is null then
    raise exception 'Say how much cash they will pay with';
  end if;

  insert into public.orders (
    client_token, ref, restaurant_id, customer_name, phone, area, address,
    lat, lng, note, pay_method, pays_with_cents, transfer_status,
    food_cents, fee_cents, due_at, test, checkout_id
  ) values (
    token,
    pidi.make_ref(),
    rest.id,
    payload ->> 'name',
    regexp_replace(payload ->> 'phone', '\D', '', 'g'),
    coalesce(payload ->> 'area', ''),
    payload ->> 'address',
    nullif(payload ->> 'lat', '')::float8,
    nullif(payload ->> 'lng', '')::float8,
    coalesce(payload ->> 'note', ''),
    pay::public.pay_method,
    pays,
    case when pay = 'transfer' and fee = 500 then coalesce(nullif(payload ->> 'transfer_status', ''), 'awaiting')::public.transfer_status else null end,
    food,
    fee,
    due,
    coalesce((payload ->> 'test')::boolean, false),
    checkout
  ) returning * into row;

  for item in select value from jsonb_array_elements(payload -> 'items')
  loop
    insert into public.order_items (order_id, name, qty, price_cents)
    values (row.id, item ->> 'name', (item ->> 'qty')::int, (item ->> 'price_cents')::int);
  end loop;

  return pidi.order_public(row.id);
end;
$$;

create function pidi.order_public(order_id uuid) returns jsonb
language sql stable
security definer
set search_path = ''
as $$
  select jsonb_build_object(
    'id', o.id,
    'public_token', o.public_token,
    'ref', o.ref,
    'status', o.status,
    'restaurant', r.name,
    'restaurant_slug', r.slug,
    'food_cents', o.food_cents,
    'fee_cents', o.fee_cents,
    'total_cents', o.total_cents,
    'change_due_cents', o.change_due_cents,
    'pay', o.pay_method,
    'outside_hours', o.outside_hours
  )
  from public.orders o
  join public.restaurants r on r.id = o.restaurant_id
  where o.id = order_public.order_id
$$;

-- One checkout, one or two restaurants, one ƒ5 fee, food total at least ƒ24.
create function pidi.place_checkout(payload jsonb) returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  groups jsonb := payload -> 'groups';
  n int;
  i int;
  food int := 0;
  item jsonb;
  group_food int;
  checkout uuid := gen_random_uuid();
  made jsonb := '[]'::jsonb;
  one jsonb;
  client text := nullif(payload ->> 'client_token', '');
  existing uuid;
begin
  if client is not null then
    select checkout_id into existing from public.orders where client_token = client || ':0';
    if found then
      return (
        select jsonb_build_object(
          'checkout_id', existing,
          'orders', coalesce(jsonb_agg(pidi.order_public(id) order by created_at), '[]'::jsonb)
        )
        from public.orders where checkout_id = existing
      );
    end if;
  end if;
  if jsonb_typeof(groups) <> 'array' then
    raise exception 'Add the restaurants';
  end if;
  n := jsonb_array_length(groups);
  if n < 1 or n > 2 then
    raise exception 'One checkout can hold one or two restaurants';
  end if;
  for i in 0..(n - 1) loop
    group_food := 0;
    if jsonb_typeof(groups -> i -> 'items') <> 'array' then
      raise exception 'Each restaurant needs its dishes';
    end if;
    for item in select value from jsonb_array_elements(groups -> i -> 'items') loop
      group_food := group_food + (item ->> 'qty')::int * (item ->> 'price_cents')::int;
    end loop;
    food := food + group_food;
  end loop;
  if food < 2400 then
    raise exception 'The food minimum is ƒ24 before the delivery fee';
  end if;
  perform set_config('pidi.checkout', 'on', true);

  for i in 0..(n - 1) loop
    one := payload || jsonb_build_object(
      'restaurant', groups -> i ->> 'restaurant',
      'items', groups -> i -> 'items',
      'client_token', case when client is null then null else client || ':' || i end,
      'checkout_id', checkout,
      'fee_cents', case when i = 0 then 500 else 0 end,
      'pays_with_cents', case when i = 0 then payload -> 'pays_with_cents' else 'null'::jsonb end,
      'transfer_status', case when i = 0 then payload -> 'transfer_status' else 'null'::jsonb end
    );
    made := made || jsonb_build_array(pidi.place_order(one));
  end loop;
  return jsonb_build_object('checkout_id', checkout, 'orders', made);
end;
$$;

create function pidi.order_by_token(token text) returns jsonb
language plpgsql stable
security definer
set search_path = ''
as $$
declare
  row public.orders%rowtype;
  label text;
begin
  select * into row from public.orders where public_token = token;
  if not found then
    return null;
  end if;
  label := case row.status
    when 'new' then 'Received'
    when 'accepted' then 'Received'
    when 'cooking' then 'Cooking'
    when 'ready' then 'Cooking'
    when 'assigned' then 'On the way'
    when 'picked_up' then 'On the way'
    when 'delivered' then 'Delivered'
    when 'cancelled' then 'Cancelled'
    else 'Received'
  end;
  return jsonb_build_object(
    'id', row.id,
    'status', row.status,
    'label', label,
    'ref', row.ref,
    'restaurant', (select name from public.restaurants where id = row.restaurant_id),
    'outside_hours', row.outside_hours
  );
end;
$$;

-- ---------------------------------------------------------------------------
-- PIN checks. Called with the service role from an Edge Function, not the browser.
-- ---------------------------------------------------------------------------

create function pidi.check_pin(kind text, code text, pin text) returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  rec record;
  digits text := regexp_replace(coalesce(pin, ''), '\D', '', 'g');
begin
  if code is null or length(digits) < 4 or length(digits) > 8 then
    return jsonb_build_object('error', 'no');
  end if;
  if kind = 'driver' then
    select id, name, drivers.code, pin_hash, active, pin_failures, pin_locked_until
      into rec from public.drivers where drivers.code = check_pin.code;
  else
    select id, name, staff.code, pin_hash, active, pin_failures, pin_locked_until
      into rec from public.staff where staff.code = check_pin.code;
  end if;
  if not found or rec.active is not true then
    return jsonb_build_object('error', 'no');
  end if;
  if rec.pin_locked_until is not null and rec.pin_locked_until > now() then
    return jsonb_build_object('error', 'locked');
  end if;
  if not pidi.pin_ok(digits, rec.pin_hash) then
    if kind = 'driver' then
      update public.drivers
        set pin_failures = drivers.pin_failures + 1,
            pin_locked_until = case when drivers.pin_failures + 1 >= 5 then now() + interval '5 minutes' else null end
        where id = rec.id;
    else
      update public.staff
        set pin_failures = staff.pin_failures + 1,
            pin_locked_until = case when staff.pin_failures + 1 >= 5 then now() + interval '5 minutes' else null end
        where id = rec.id;
    end if;
    return jsonb_build_object('error', 'no');
  end if;
  if kind = 'driver' then
    update public.drivers set pin_failures = 0, pin_locked_until = null where id = rec.id;
  else
    update public.staff set pin_failures = 0, pin_locked_until = null where id = rec.id;
  end if;
  return jsonb_build_object('id', rec.id, 'name', rec.name, 'code', rec.code);
end;
$$;

create function pidi.verify_driver_pin(code text, pin text) returns jsonb
language sql security definer set search_path = ''
as $$ select pidi.check_pin('driver', code, pin) $$;

create function pidi.verify_kitchen_pin(code text, pin text) returns jsonb
language sql security definer set search_path = ''
as $$ select pidi.check_pin('kitchen', code, pin) $$;

-- ---------------------------------------------------------------------------
-- Dispatch
--
-- When an order is ready (or, if settings.dispatch_when is 'accepted', as soon
-- as the kitchen accepts it), build one run of 1 or 2 orders and offer it to
-- every online driver who is not already on a run.
--
-- Pairing: a second order joins the run when it is ready, or due within
-- pair_minutes (default 10), AND it is nearby: the same area, or under
-- pair_km (default 3) between the two drop pins. The closer pin to the pickup
-- point is stop 1 when a pickup pin is set. Otherwise the earlier due time is stop 1.
--
-- The first driver whose accept updates the run from 'offered' to 'active' wins.
-- The run row is locked. A late accept finds the run no longer offered.
--
-- An offer lasts offer_seconds (default 45). accept_offer refuses an expired
-- row. dispatch_tick marks those rows expired and writes a fresh offer for
-- online drivers who have not declined this run. A driver phone calls
-- dispatch_tick while it is online, and pg_cron calls it every 15 seconds when
-- the extension is on. Supabase Cron can run that often on the free tier.
-- If cron is not turned on, the next phone poll still re-offers.
-- ---------------------------------------------------------------------------

create function pidi.dispatch_statuses() returns public.order_status[]
language sql stable
set search_path = ''
as $$
  select case when coalesce(pidi.setting('dispatch_when'), 'ready') = 'accepted'
    then array['accepted', 'cooking', 'ready']::public.order_status[]
    else array['ready']::public.order_status[]
  end
$$;

create function pidi.live_order(order_id uuid) returns boolean
language sql stable
set search_path = ''
as $$
  select exists (
    select 1 from public.run_orders ro
    join public.runs r on r.id = ro.run_id
    where ro.order_id = live_order.order_id
      and r.status in ('offered', 'active')
  )
$$;

create function pidi.nearby(a public.orders, b public.orders) returns boolean
language plpgsql stable
set search_path = ''
as $$
declare
  minutes int := greatest(coalesce(pidi.setting('pair_minutes')::int, 10), 1);
  km_max float8 := coalesce(pidi.setting('pair_km')::float8, 3);
  close_enough boolean := false;
  due_ok boolean;
begin
  due_ok := a.status = 'ready' or b.status = 'ready'
    or abs(extract(epoch from (a.due_at - b.due_at))) <= minutes * 60;
  if not due_ok then
    return false;
  end if;
  if a.area <> '' and lower(a.area) = lower(b.area) then
    close_enough := true;
  end if;
  if a.lat is not null and b.lat is not null and pidi.km(a.lat, a.lng, b.lat, b.lng) < km_max then
    close_enough := true;
  end if;
  return close_enough;
end;
$$;

create function pidi.free_drivers() returns setof uuid
language sql stable
set search_path = ''
as $$
  select d.id
  from public.drivers d
  where d.online and d.active
    and not exists (
      select 1 from public.runs r
      where r.driver_id = d.id and r.status = 'active'
    )
$$;

create function pidi.offer_run(run_id uuid) returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  seconds int := greatest(coalesce(pidi.setting('offer_seconds')::int, 45), 15);
  driver uuid;
begin
  for driver in select pidi.free_drivers()
  loop
    if exists (
      select 1 from public.offers
      where offers.run_id = offer_run.run_id
        and offers.driver_id = driver
        and offers.status = 'declined'
    ) then
      continue;
    end if;
    if exists (
      select 1 from public.offers
      where offers.run_id = offer_run.run_id
        and offers.driver_id = driver
        and offers.status = 'pending'
        and offers.expires_at > now()
    ) then
      continue;
    end if;
    update public.offers
      set status = 'expired'
      where offers.run_id = offer_run.run_id
        and offers.driver_id = driver
        and offers.status = 'pending';
    insert into public.offers (run_id, driver_id, status, expires_at)
    values (offer_run.run_id, driver, 'pending', now() + make_interval(secs => seconds));
  end loop;
end;
$$;

create function pidi.create_run(first_id uuid, second_id uuid) returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  run_id uuid;
  a public.orders%rowtype;
  b public.orders%rowtype;
  plat float8;
  plng float8;
  a_first boolean := true;
begin
  select * into a from public.orders where id = first_id for update;
  if second_id is not null then
    select * into b from public.orders where id = second_id for update;
  end if;
  if pidi.live_order(a.id) or (second_id is not null and pidi.live_order(b.id)) then
    return null;
  end if;

  plat := nullif(pidi.setting('pickup_lat'), '')::float8;
  plng := nullif(pidi.setting('pickup_lng'), '')::float8;
  if second_id is not null and plat is not null and plng is not null and a.lat is not null and b.lat is not null then
    a_first := pidi.km(plat, plng, a.lat, a.lng) <= pidi.km(plat, plng, b.lat, b.lng);
  elsif second_id is not null and b.due_at < a.due_at then
    a_first := false;
  end if;

  insert into public.runs (status) values ('offered') returning id into run_id;
  if second_id is null or a_first then
    insert into public.run_orders (run_id, order_id, stop_index) values (run_id, a.id, 1);
    if second_id is not null then
      insert into public.run_orders (run_id, order_id, stop_index) values (run_id, b.id, 2);
    end if;
  else
    insert into public.run_orders (run_id, order_id, stop_index) values (run_id, b.id, 1);
    insert into public.run_orders (run_id, order_id, stop_index) values (run_id, a.id, 2);
  end if;
  perform pidi.offer_run(run_id);
  return run_id;
end;
$$;

-- A second nearby order can still join a run that nobody has accepted.
create function pidi.attach_to_offered(order_id uuid) returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  rec public.orders%rowtype;
  host_run uuid;
begin
  select * into rec from public.orders where id = attach_to_offered.order_id for update;
  if rec.id is null or pidi.live_order(rec.id) then
    return null;
  end if;
  select r.id into host_run
  from public.runs r
  join public.run_orders ro on ro.run_id = r.id
  join public.orders host on host.id = ro.order_id
  where r.status = 'offered'
    and (select count(*) from public.run_orders x where x.run_id = r.id) = 1
    and pidi.nearby(rec, host)
  order by host.due_at
  limit 1
  for update of r;
  if host_run is null then
    return null;
  end if;
  if (select count(*) from public.run_orders x where x.run_id = host_run) <> 1 then
    return null;
  end if;
  insert into public.run_orders (run_id, order_id, stop_index)
  values (host_run, rec.id, 2);
  update public.offers
    set status = 'expired'
    where offers.run_id = host_run and status = 'pending';
  perform pidi.offer_run(host_run);
  return host_run;
end;
$$;

create function pidi.dispatch_tick() returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  rec public.orders%rowtype;
  partner uuid;
  other public.orders%rowtype;
  run_id uuid;
begin
  perform pg_advisory_xact_lock(hashtext('pidi-dispatch'));

  update public.offers
    set status = 'expired'
    where status = 'pending' and expires_at <= now();

  for run_id in
    select r.id from public.runs r
    where r.status = 'offered'
      and not exists (
        select 1 from public.offers o
        where o.run_id = r.id and o.status = 'pending' and o.expires_at > now()
      )
  loop
    perform pidi.offer_run(run_id);
  end loop;

  for rec in
    select o.*
    from public.orders o
    where o.status = any (pidi.dispatch_statuses())
      and not pidi.live_order(o.id)
    order by o.due_at, o.created_at
    for update skip locked
  loop
    if pidi.live_order(rec.id) then
      continue;
    end if;
    partner := null;
    if pidi.attach_to_offered(rec.id) is not null then
      continue;
    end if;
    for other in
      select o2.*
      from public.orders o2
      where o2.id <> rec.id
        and o2.status = any (pidi.dispatch_statuses())
        and not pidi.live_order(o2.id)
      order by o2.due_at
    loop
      if pidi.nearby(rec, other) then
        partner := other.id;
        exit;
      end if;
    end loop;
    perform pidi.create_run(rec.id, partner);
  end loop;
end;
$$;

create function pidi.accept_offer(offer_id uuid) returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  off public.offers%rowtype;
  won public.runs%rowtype;
  me uuid := pidi.driver_id();
begin
  if me is null then
    return jsonb_build_object('ok', false, 'error', 'Sign in again');
  end if;
  perform pg_advisory_xact_lock(hashtext('pidi-dispatch'));

  select * into off from public.offers where id = accept_offer.offer_id for update;
  if not found or off.driver_id <> me then
    return jsonb_build_object('ok', false, 'error', 'That offer is not yours');
  end if;
  if off.status = 'lost' then
    return jsonb_build_object('ok', false, 'error', 'Another driver took this run');
  end if;
  if off.status <> 'pending' or off.expires_at <= now() then
    if off.status = 'pending' then
      update public.offers set status = 'expired' where id = off.id;
    end if;
    return jsonb_build_object('ok', false, 'error', 'That offer expired');
  end if;

  update public.runs
    set status = 'active', driver_id = me, accepted_at = now()
    where id = off.run_id and status = 'offered'
    returning * into won;

  if not found then
    update public.offers set status = 'lost' where id = off.id and status = 'pending';
    return jsonb_build_object('ok', false, 'error', 'Another driver took this run');
  end if;

  update public.offers set status = 'accepted' where id = off.id;
  update public.offers set status = 'lost'
    where run_id = off.run_id and id <> off.id and status = 'pending';

  perform set_config('pidi.actor', 'dispatch', true);
  update public.orders
    set status = 'assigned'
    where id in (select order_id from public.run_orders where run_id = won.id)
      and status = any (pidi.dispatch_statuses());

  return jsonb_build_object('ok', true, 'run_id', won.id);
end;
$$;

create function pidi.decline_offer(offer_id uuid) returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  me uuid := pidi.driver_id();
begin
  update public.offers
    set status = 'declined'
    where id = decline_offer.offer_id
      and driver_id = me
      and status = 'pending';
  if not found then
    return jsonb_build_object('ok', false);
  end if;
  perform pidi.dispatch_tick();
  return jsonb_build_object('ok', true);
end;
$$;

create function pidi.go_online() returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  me uuid := pidi.driver_id();
begin
  update public.drivers set online = true where id = me and active;
  if not found then
    return jsonb_build_object('ok', false);
  end if;
  perform pidi.dispatch_tick();
  return jsonb_build_object('ok', true, 'online', true);
end;
$$;

create function pidi.go_offline() returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  me uuid := pidi.driver_id();
begin
  update public.drivers set online = false where id = me;
  update public.offers set status = 'expired'
    where driver_id = me and status = 'pending';
  return jsonb_build_object('ok', true, 'online', false);
end;
$$;

create function pidi.my_offers() returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  me uuid := pidi.driver_id();
begin
  if me is null then
    return '[]'::jsonb;
  end if;
  perform pidi.dispatch_tick();
  return coalesce((
    select jsonb_agg(jsonb_build_object(
      'offer_id', o.id,
      'run_id', o.run_id,
      'expires_at', o.expires_at,
      'seconds_left', greatest(0, ceil(extract(epoch from (o.expires_at - now())))::int),
      'stops', (
        select jsonb_agg(jsonb_build_object(
          'stop', ro.stop_index,
          'name', ord.customer_name,
          'area', ord.area,
          'restaurant', rest.name,
          'pay', ord.pay_method,
          'total_cents', ord.total_cents,
          'transfer_status', ord.transfer_status
        ) order by ro.stop_index)
        from public.run_orders ro
        join public.orders ord on ord.id = ro.order_id
        join public.restaurants rest on rest.id = ord.restaurant_id
        where ro.run_id = o.run_id
      )
    ) order by o.expires_at)
    from public.offers o
    where o.driver_id = me and o.status = 'pending' and o.expires_at > now()
  ), '[]'::jsonb);
end;
$$;

create function pidi.run_detail(run_id uuid) returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  me uuid := pidi.driver_id();
  run public.runs%rowtype;
begin
  select * into run from public.runs where id = run_detail.run_id;
  if not found or run.driver_id is distinct from me then
    if not pidi.is_kitchen() then
      return null;
    end if;
  end if;
  return jsonb_build_object(
    'id', run.id,
    'status', run.status,
    'step', run.step,
    'drop_index', run.drop_index,
    'pickup', jsonb_build_object(
      'name', coalesce(pidi.setting('pickup_name'), ''),
      'address', coalesce(pidi.setting('pickup_address'), ''),
      'lat', nullif(pidi.setting('pickup_lat'), ''),
      'lng', nullif(pidi.setting('pickup_lng'), '')
    ),
    'stops', (
      select jsonb_agg(jsonb_build_object(
        'stop', ro.stop_index,
        'order_id', ord.id,
        'status', ord.status,
        'name', ord.customer_name,
        'phone', ord.phone,
        'area', ord.area,
        'address', ord.address,
        'lat', ord.lat,
        'lng', ord.lng,
        'note', ord.note,
        'pay', ord.pay_method,
        'pays_with_cents', ord.pays_with_cents,
        'change_due_cents', ord.change_due_cents,
        'total_cents', ord.total_cents,
        'transfer_status', ord.transfer_status,
        'restaurant', rest.name,
        'restaurant_slug', rest.slug,
        'items', (
          select coalesce(jsonb_agg(jsonb_build_object('name', i.name, 'qty', i.qty) order by i.name), '[]'::jsonb)
          from public.order_items i where i.order_id = ord.id
        )
      ) order by ro.stop_index)
      from public.run_orders ro
      join public.orders ord on ord.id = ro.order_id
      join public.restaurants rest on rest.id = ord.restaurant_id
      where ro.run_id = run.id
    )
  );
end;
$$;

create function pidi.advance_run(run_id uuid, action text) returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  me uuid := pidi.driver_id();
  run public.runs%rowtype;
  current_order uuid;
  remaining int;
begin
  select * into run from public.runs where id = advance_run.run_id and driver_id = me and status = 'active' for update;
  if not found then
    return jsonb_build_object('ok', false, 'error', 'This run is not yours');
  end if;
  perform set_config('pidi.actor', 'driver', true);

  if action = 'picked_up' then
    if run.step <> 'pickup' then
      return jsonb_build_object('ok', false, 'error', 'Already picked up');
    end if;
    update public.orders set status = 'picked_up'
      where id in (select order_id from public.run_orders where run_id = run.id)
        and status = 'assigned';
    update public.runs set step = 'drop', drop_index = 0 where id = run.id;
  elsif action = 'delivered' then
    if run.step <> 'drop' then
      return jsonb_build_object('ok', false, 'error', 'Pick up first');
    end if;
    select order_id into current_order
      from public.run_orders
      where run_id = run.id and stop_index = run.drop_index + 1;
    update public.orders set status = 'delivered' where id = current_order and status = 'picked_up';
    select count(*) into remaining
      from public.run_orders ro
      join public.orders o on o.id = ro.order_id
      where ro.run_id = run.id and o.status <> 'delivered';
    if remaining = 0 then
      update public.runs set step = 'done', status = 'done', finished_at = now() where id = run.id;
    else
      update public.runs set drop_index = drop_index + 1 where id = run.id;
    end if;
  else
    return jsonb_build_object('ok', false, 'error', 'Unknown step');
  end if;
  return pidi.run_detail(run.id);
end;
$$;

create function pidi.push_location(lat float8, lng float8) returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  me uuid := pidi.driver_id();
  run_id uuid;
  recent timestamptz;
begin
  if me is null or lat is null or lng is null then
    return jsonb_build_object('ok', false);
  end if;
  select id into run_id from public.runs where driver_id = me and status = 'active' limit 1;
  if run_id is null then
    return jsonb_build_object('ok', false, 'error', 'Not on a run');
  end if;
  select recorded_at into recent from public.driver_locations where driver_id = me;
  if recent is not null and recent > now() - interval '8 seconds' then
    return jsonb_build_object('ok', true, 'throttled', true);
  end if;
  insert into public.driver_locations (driver_id, run_id, lat, lng, recorded_at)
  values (me, run_id, lat, lng, now())
  on conflict (driver_id) do update
    set run_id = excluded.run_id, lat = excluded.lat, lng = excluded.lng, recorded_at = excluded.recorded_at;
  return jsonb_build_object('ok', true, 'throttled', false);
end;
$$;

create function pidi.kitchen_set_status(order_id uuid, next_status public.order_status) returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  row public.orders%rowtype;
begin
  if not pidi.is_kitchen() then
    return jsonb_build_object('ok', false, 'error', 'Kitchen sign-in required');
  end if;
  perform set_config('pidi.actor', 'kitchen', true);
  update public.orders set status = next_status where id = kitchen_set_status.order_id returning * into row;
  if not found then
    return jsonb_build_object('ok', false, 'error', 'No such order');
  end if;
  if next_status = 'cancelled' then
    update public.runs r
      set status = 'cancelled'
      where r.status = 'offered'
        and exists (select 1 from public.run_orders ro where ro.run_id = r.id and ro.order_id = row.id);
    delete from public.run_orders ro
      using public.runs r
      where ro.run_id = r.id and r.status = 'cancelled' and ro.order_id = row.id;
  elsif next_status in ('accepted', 'cooking', 'ready') then
    perform pidi.dispatch_tick();
  end if;
  return jsonb_build_object('ok', true, 'status', row.status);
end;
$$;

-- ---------------------------------------------------------------------------
-- Public API. Thin wrappers so PostgREST can call them. Logic stays in pidi.
-- ---------------------------------------------------------------------------

create function public.place_order(payload jsonb) returns jsonb
language sql security invoker set search_path = ''
as $$ select pidi.place_order(payload) $$;

create function public.place_checkout(payload jsonb) returns jsonb
language sql security invoker set search_path = ''
as $$ select pidi.place_checkout(payload) $$;

create function public.order_by_token(token text) returns jsonb
language sql security invoker set search_path = ''
as $$ select pidi.order_by_token(token) $$;

create function public.verify_driver_pin(code text, pin text) returns jsonb
language sql security invoker set search_path = ''
as $$ select pidi.verify_driver_pin(code, pin) $$;

create function public.verify_kitchen_pin(code text, pin text) returns jsonb
language sql security invoker set search_path = ''
as $$ select pidi.verify_kitchen_pin(code, pin) $$;

create function public.dispatch_tick() returns void
language sql security invoker set search_path = ''
as $$ select pidi.dispatch_tick() $$;

create function public.accept_offer(offer_id uuid) returns jsonb
language sql security invoker set search_path = ''
as $$ select pidi.accept_offer(offer_id) $$;

create function public.decline_offer(offer_id uuid) returns jsonb
language sql security invoker set search_path = ''
as $$ select pidi.decline_offer(offer_id) $$;

create function public.go_online() returns jsonb
language sql security invoker set search_path = ''
as $$ select pidi.go_online() $$;

create function public.go_offline() returns jsonb
language sql security invoker set search_path = ''
as $$ select pidi.go_offline() $$;

create function public.my_offers() returns jsonb
language sql security invoker set search_path = ''
as $$ select pidi.my_offers() $$;

create function public.run_detail(run_id uuid) returns jsonb
language sql security invoker set search_path = ''
as $$ select pidi.run_detail(run_id) $$;

create function public.advance_run(run_id uuid, action text) returns jsonb
language sql security invoker set search_path = ''
as $$ select pidi.advance_run(run_id, action) $$;

create function public.push_location(lat float8, lng float8) returns jsonb
language sql security invoker set search_path = ''
as $$ select pidi.push_location(lat, lng) $$;

create function public.kitchen_set_status(order_id uuid, next_status public.order_status) returns jsonb
language sql security invoker set search_path = ''
as $$ select pidi.kitchen_set_status(order_id, next_status) $$;

revoke all on function public.place_order(jsonb) from public;
revoke all on function public.place_checkout(jsonb) from public;
revoke all on function public.order_by_token(text) from public;
revoke all on function public.verify_driver_pin(text, text) from public;
revoke all on function public.verify_kitchen_pin(text, text) from public;
revoke all on function public.dispatch_tick() from public;
revoke all on function public.accept_offer(uuid) from public;
revoke all on function public.decline_offer(uuid) from public;
revoke all on function public.go_online() from public;
revoke all on function public.go_offline() from public;
revoke all on function public.my_offers() from public;
revoke all on function public.run_detail(uuid) from public;
revoke all on function public.advance_run(uuid, text) from public;
revoke all on function public.push_location(float8, float8) from public;
revoke all on function public.kitchen_set_status(uuid, public.order_status) from public;

grant execute on function public.place_order(jsonb) to anon, authenticated;
grant execute on function public.place_checkout(jsonb) to anon, authenticated;
grant execute on function public.order_by_token(text) to anon, authenticated;
grant execute on function public.verify_driver_pin(text, text) to service_role;
grant execute on function public.verify_kitchen_pin(text, text) to service_role;
grant execute on function public.dispatch_tick() to authenticated, service_role;
grant execute on function public.accept_offer(uuid) to authenticated;
grant execute on function public.decline_offer(uuid) to authenticated;
grant execute on function public.go_online() to authenticated;
grant execute on function public.go_offline() to authenticated;
grant execute on function public.my_offers() to authenticated;
grant execute on function public.run_detail(uuid) to authenticated;
grant execute on function public.advance_run(uuid, text) to authenticated;
grant execute on function public.push_location(float8, float8) to authenticated;
grant execute on function public.kitchen_set_status(uuid, public.order_status) to authenticated;

grant execute on function pidi.place_order(jsonb) to anon, authenticated;
grant execute on function pidi.place_checkout(jsonb) to anon, authenticated;
grant execute on function pidi.order_by_token(text) to anon, authenticated;
grant execute on function pidi.verify_driver_pin(text, text) to service_role;
grant execute on function pidi.verify_kitchen_pin(text, text) to service_role;
grant execute on function pidi.dispatch_tick() to authenticated, service_role;
grant execute on function pidi.accept_offer(uuid) to authenticated;
grant execute on function pidi.decline_offer(uuid) to authenticated;
grant execute on function pidi.go_online() to authenticated;
grant execute on function pidi.go_offline() to authenticated;
grant execute on function pidi.my_offers() to authenticated;
grant execute on function pidi.run_detail(uuid) to authenticated;
grant execute on function pidi.advance_run(uuid, text) to authenticated;
grant execute on function pidi.push_location(float8, float8) to authenticated;
grant execute on function pidi.kitchen_set_status(uuid, public.order_status) to authenticated;

revoke all on all functions in schema pidi from public;
grant execute on function pidi.is_kitchen() to anon, authenticated;
grant execute on function pidi.driver_id() to anon, authenticated;

-- ---------------------------------------------------------------------------
-- Grants and row level security
-- ---------------------------------------------------------------------------

revoke all on all tables in schema public from anon, authenticated;
grant select on public.restaurants to anon, authenticated;
grant select (id, name, code, online, active) on public.drivers to authenticated;
grant select (id, name, code, active) on public.staff to authenticated;
grant select on public.settings to anon, authenticated;
grant select on public.orders to anon, authenticated;
grant select on public.order_items to anon, authenticated;
grant select on public.order_events to authenticated;
grant select on public.runs to authenticated;
grant select on public.run_orders to authenticated;
grant select on public.offers to authenticated;
grant select on public.driver_locations to authenticated;
grant update (status, transfer_status) on public.orders to authenticated;

alter table public.restaurants enable row level security;
alter table public.staff enable row level security;
alter table public.drivers enable row level security;
alter table public.settings enable row level security;
alter table public.orders enable row level security;
alter table public.order_items enable row level security;
alter table public.order_events enable row level security;
alter table public.runs enable row level security;
alter table public.run_orders enable row level security;
alter table public.offers enable row level security;
alter table public.driver_locations enable row level security;

create policy restaurants_read on public.restaurants
  for select to anon, authenticated using (active);

create policy settings_public on public.settings
  for select to anon using (is_public);
create policy settings_staff on public.settings
  for select to authenticated
  using ((select pidi.is_kitchen()) or (select pidi.driver_id()) is not null);

create policy drivers_self on public.drivers
  for select to authenticated
  using (id = (select pidi.driver_id()) or (select pidi.is_kitchen()));
create policy staff_self on public.staff
  for select to authenticated
  using (
    id = nullif((select auth.jwt() ->> 'staff_id'), '')::uuid
    or (select pidi.is_kitchen())
  );

create policy orders_by_token on public.orders
  for select to anon, authenticated
  using (public_token = nullif((select auth.jwt() ->> 'order_token'), ''));
create policy orders_kitchen on public.orders
  for select to authenticated
  using ((select pidi.is_kitchen()));
create policy orders_driver on public.orders
  for select to authenticated
  using (
    exists (
      select 1 from public.run_orders ro
      join public.runs r on r.id = ro.run_id
      where ro.order_id = orders.id
        and r.driver_id = (select pidi.driver_id())
        and r.status in ('active', 'done')
    )
  );
create policy orders_kitchen_update on public.orders
  for update to authenticated
  using ((select pidi.is_kitchen()))
  with check ((select pidi.is_kitchen()));
create policy orders_driver_update on public.orders
  for update to authenticated
  using (
    exists (
      select 1 from public.run_orders ro
      join public.runs r on r.id = ro.run_id
      where ro.order_id = orders.id
        and r.driver_id = (select pidi.driver_id())
        and r.status = 'active'
    )
  )
  with check (
    exists (
      select 1 from public.run_orders ro
      join public.runs r on r.id = ro.run_id
      where ro.order_id = orders.id
        and r.driver_id = (select pidi.driver_id())
        and r.status = 'active'
    )
  );

create policy items_by_token on public.order_items
  for select to anon, authenticated
  using (
    exists (
      select 1 from public.orders o
      where o.id = order_items.order_id
        and o.public_token = nullif((select auth.jwt() ->> 'order_token'), '')
    )
  );
create policy items_kitchen on public.order_items
  for select to authenticated using ((select pidi.is_kitchen()));
create policy items_driver on public.order_items
  for select to authenticated
  using (
    exists (
      select 1 from public.run_orders ro
      join public.runs r on r.id = ro.run_id
      where ro.order_id = order_items.order_id
        and r.driver_id = (select pidi.driver_id())
        and r.status in ('active', 'done')
    )
  );

create policy events_kitchen on public.order_events
  for select to authenticated using ((select pidi.is_kitchen()));
create policy events_driver on public.order_events
  for select to authenticated
  using (
    exists (
      select 1 from public.run_orders ro
      join public.runs r on r.id = ro.run_id
      where ro.order_id = order_events.order_id
        and r.driver_id = (select pidi.driver_id())
        and r.status in ('active', 'done')
    )
  );

create policy runs_driver on public.runs
  for select to authenticated
  using (driver_id = (select pidi.driver_id()) or (select pidi.is_kitchen()));
create policy run_orders_driver on public.run_orders
  for select to authenticated
  using (
    exists (
      select 1 from public.runs r
      where r.id = run_orders.run_id
        and (r.driver_id = (select pidi.driver_id()) or (select pidi.is_kitchen()))
    )
  );

create policy offers_driver on public.offers
  for select to authenticated
  using (driver_id = (select pidi.driver_id()) or (select pidi.is_kitchen()));

create policy locations_driver on public.driver_locations
  for select to authenticated
  using (driver_id = (select pidi.driver_id()) or (select pidi.is_kitchen()));
create policy locations_customer on public.driver_locations
  for select to anon, authenticated
  using (
    exists (
      select 1
      from public.orders o
      join public.run_orders ro on ro.order_id = o.id
      join public.runs r on r.id = ro.run_id
      where o.public_token = nullif((select auth.jwt() ->> 'order_token'), '')
        and r.driver_id = driver_locations.driver_id
        and o.status in ('picked_up', 'delivered')
    )
  );

-- ---------------------------------------------------------------------------
-- Realtime. Hosted Supabase already has the publication. Plain Postgres does not.
-- ---------------------------------------------------------------------------

alter table public.orders replica identity full;
alter table public.runs replica identity full;
alter table public.offers replica identity full;
alter table public.driver_locations replica identity full;

do $pub$
declare
  t text;
begin
  if not exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    raise notice 'supabase_realtime is not on this server. Hosted Supabase already has it. Add orders, runs, offers and driver_locations there.';
    return;
  end if;
  foreach t in array array['orders', 'runs', 'offers', 'driver_locations']
  loop
    if not exists (
      select 1 from pg_publication_tables
      where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = t
    ) then
      execute format('alter publication supabase_realtime add table public.%I', t);
    end if;
  end loop;
end
$pub$;

-- 15 seconds, so a 45 second offer is re-offered without waiting on a phone.
-- Skipped when pg_cron is not installed. Driver polls call dispatch_tick anyway.
do $cron$
begin
  if to_regnamespace('cron') is null then
    raise notice 'pg_cron is not installed. Offers still re-open on the next driver poll.';
    return;
  end if;
  if not exists (select 1 from cron.job where jobname = 'pidi-dispatch-tick') then
    perform cron.schedule('pidi-dispatch-tick', '15 seconds', 'select public.dispatch_tick()');
  end if;
exception when others then
  raise notice 'pg_cron schedule skipped: %', sqlerrm;
end
$cron$;
