-- Prices from the database, 16 Oct 2026, for a database set up before it. Paste all of it into the Supabase
-- SQL editor of the Pidi project and press Run. Safe to run twice. In any other project it stops at the first
-- check and changes nothing. Run SETTINGS_2026-10-16.sql first (and PIN_FIX_2026-10-16.sql if it isn't in yet).
--
-- Until now an order kept the prices the customer's phone sent. After this paste the database works out every
-- price itself, from a copy of the website's menus (the new pidi_menu table): the dish, plus the extra price of
-- each option the line names. It refuses a dish that isn't on the menu (BAD_ITEM), a sold-out dish (SOLD_OUT)
-- and a restaurant set to "Opening soon" or hidden (REST_CLOSED). The kitchen app fills that copy by itself
-- when the chef signs in to Orders, when the website's menu changes, and right after a save on the Menu tile.
-- A restaurant with no menu here yet keeps the old rule (the phone's prices) until the kitchen app sends it.
-- Nothing is removed: a dish taken off the menu is only marked as not listed.

begin;

-- Stops here, changing nothing, when this isn't the Pidi database.
do $guard$ begin
  if to_regclass('public.pidi_orders') is null or to_regclass('public.pidi_settings') is null then
    raise exception 'This is not the Pidi database (no pidi_orders table). Nothing was changed.';
  end if;
end $guard$;

-- The menu the database prices every order from: one row per dish, as the website's menu.json has it. The
-- kitchen app sends it (pidi_kitchen_sync_menu). A dish taken off the menu stays as a row with listed false;
-- nothing is ever removed. options keeps each option's choices and their extra price in cents.
create table if not exists public.pidi_menu (
  restaurant_id uuid not null references public.pidi_restaurants (id),
  item_id text not null,
  name text not null,
  price_cents integer not null,
  sold_out boolean not null default false,
  listed boolean not null default true,
  includes jsonb not null default '[]'::jsonb,
  options jsonb not null default '[]'::jsonb,
  updated_at timestamptz not null default now(),
  constraint pidi_menu_pk primary key (restaurant_id, item_id),
  constraint pidi_menu_price check (price_cents >= 0 and price_cents <= 100000)
);

-- open / soon / hidden, as site.json says (null until the kitchen app first sends it), and when the menu
-- last came in: from the website, or straight from a save on the kitchen app's Menu tile.
alter table public.pidi_restaurants add column if not exists menu_status text;
alter table public.pidi_restaurants add column if not exists menu_synced_at timestamptz;
alter table public.pidi_restaurants add column if not exists menu_saved_at timestamptz;

alter table public.pidi_menu enable row level security;

do $pidi_menu_rls$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'pidi_menu' and policyname = 'pidi_menu_no_select'
  ) then
    create policy pidi_menu_no_select on public.pidi_menu for all to anon using (false) with check (false);
  end if;
end
$pidi_menu_rls$;

-- Supabase gives anon and authenticated all rights on every new table by default.
-- Take them back on pidi_ tables: the apps reach the data through functions only.
do $pidi_table_rights$
declare
  t text;
  who text;
begin
  for t in
    select c.relname
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public' and c.relkind = 'r' and c.relname like 'pidi\_%' escape '\'
  loop
    foreach who in array array['anon', 'authenticated'] loop
      if exists (select 1 from pg_roles where rolname = who) then
        execute format('revoke all on table public.%I from %I', t, who);
      end if;
    end loop;
  end loop;
end
$pidi_table_rights$;

-- Words compared the way people type them: capitals, extra spaces and curly quotes don't matter.
create or replace function public.pidi_menu_key(t text)
returns text
language sql
immutable
set search_path = public
as $$
  select lower(trim(regexp_replace(translate(coalesce(t, ''), '‘’', ''''''), '\s+', ' ', 'g')))
$$;

-- One order line priced from the menu (pidi_menu): the dish, found by its menu id ("id") or else by its name,
-- plus the extra price of each option the line names. The options are read from the line's own words
-- ("Bitterballen (8) · Dip: Mustard", "Smash cheeseburger · No onion · No pickles", "… · No pickles, No mayo"),
-- the words the kitchen cooks from, so the price always follows what will be cooked. A one-choice option the
-- line doesn't name is the menu's default. Words that are no choice on the menu make the line BAD_ITEM.
-- Answers {"item_id", "name", "price_cents"} (the menu's own dish name) or {"error": "BAD_ITEM" | "SOLD_OUT"}.
create or replace function public.pidi_menu_price(p_rest uuid, p_line jsonb)
returns jsonb
language plpgsql
stable
security definer
set search_path = public, extensions
as $$
declare
  v_dish public.pidi_menu%rowtype;
  v_parts text[];
  v_part text;
  v_val text;
  v_grp jsonb;
  v_hit jsonb;
  v_hits jsonb := '[]'::jsonb;   -- [{"g": option id, "c": choice id, "p": extra cents}]
  v_cents integer;
  v_words text := '';
  i integer;
begin
  v_parts := string_to_array(trim(coalesce(p_line->>'name', '')), ' · ');
  if nullif(trim(coalesce(p_line->>'id', '')), '') is not null then
    select * into v_dish from public.pidi_menu m
    where m.restaurant_id = p_rest and m.item_id = trim(p_line->>'id') and m.listed;
  else
    select * into v_dish from public.pidi_menu m
    where m.restaurant_id = p_rest and m.listed
      and public.pidi_menu_key(m.name) = public.pidi_menu_key(v_parts[1])
    order by m.item_id
    limit 1;
  end if;
  if not found then
    return '{"error": "BAD_ITEM"}'::jsonb;
  end if;
  -- sold out, or a bundle (Family Table) holding a dish that is sold out
  if v_dish.sold_out or exists (
    select 1 from public.pidi_menu x
    where x.restaurant_id = p_rest and x.listed and x.sold_out and v_dish.includes ? x.item_id
  ) then
    return '{"error": "SOLD_OUT"}'::jsonb;
  end if;

  for i in 2 .. coalesce(array_length(v_parts, 1), 1)
  loop
    v_part := trim(v_parts[i]);
    if v_part = '' then
      return '{"error": "BAD_ITEM"}'::jsonb;
    end if;
    v_words := v_words || ' · ' || v_part;
    -- "Sauce: On the side", "Leave out: No onion, No egg"
    v_grp := null;
    if position(':' in v_part) > 0 then
      select g into v_grp
      from jsonb_array_elements(v_dish.options) g
      where public.pidi_menu_key(g->>'label') = public.pidi_menu_key(split_part(v_part, ':', 1))
      limit 1;
    end if;
    if v_grp is not null then
      foreach v_val in array regexp_split_to_array(trim(substr(v_part, position(':' in v_part) + 1)), '\s*,\s*')
      loop
        v_hit := null;
        select jsonb_build_object('g', v_grp->>'id', 'c', c->>'id', 'p', coalesce((c->>'price')::integer, 0)) into v_hit
        from jsonb_array_elements(v_grp->'choices') c
        where public.pidi_menu_key(c->>'label') = public.pidi_menu_key(v_val)
        limit 1;
        if v_hit is null then
          return '{"error": "BAD_ITEM"}'::jsonb;
        end if;
        v_hits := v_hits || jsonb_build_array(v_hit);
      end loop;
      continue;
    end if;
    -- "No onion" (one choice), or "No pickles, No mayo"
    v_hit := null;
    select jsonb_build_object('g', g->>'id', 'c', c->>'id', 'p', coalesce((c->>'price')::integer, 0)) into v_hit
    from jsonb_array_elements(v_dish.options) g, jsonb_array_elements(g->'choices') c
    where public.pidi_menu_key(c->>'label') = public.pidi_menu_key(v_part)
    limit 1;
    if v_hit is not null then
      v_hits := v_hits || jsonb_build_array(v_hit);
      continue;
    end if;
    foreach v_val in array regexp_split_to_array(v_part, '\s*,\s*')
    loop
      v_hit := null;
      select jsonb_build_object('g', g->>'id', 'c', c->>'id', 'p', coalesce((c->>'price')::integer, 0)) into v_hit
      from jsonb_array_elements(v_dish.options) g, jsonb_array_elements(g->'choices') c
      where public.pidi_menu_key(c->>'label') = public.pidi_menu_key(v_val)
      limit 1;
      if v_hit is null then
        return '{"error": "BAD_ITEM"}'::jsonb;
      end if;
      v_hits := v_hits || jsonb_build_array(v_hit);
    end loop;
  end loop;

  -- a one-choice option (Sauce: Tossed or On the side) takes one choice only
  if exists (
    select 1 from jsonb_array_elements(v_dish.options) g
    where g->>'type' = 'one'
      and (select count(distinct h->>'c') from jsonb_array_elements(v_hits) h where h->>'g' = g->>'id') > 1
  ) then
    return '{"error": "BAD_ITEM"}'::jsonb;
  end if;

  -- the dish, each named choice once, and the default of a one-choice option nobody named
  v_cents := v_dish.price_cents
    + (select coalesce(sum(x.p), 0) from (
         select distinct h->>'g' as g, h->>'c' as c, (h->>'p')::integer as p
         from jsonb_array_elements(v_hits) h
       ) x)
    + (select coalesce(sum(coalesce((c->>'price')::integer, 0)), 0)
       from jsonb_array_elements(v_dish.options) g, jsonb_array_elements(g->'choices') c
       where g->>'type' = 'one' and c->>'id' = g->>'default'
         and not exists (select 1 from jsonb_array_elements(v_hits) h where h->>'g' = g->>'id'));
  return jsonb_build_object('item_id', v_dish.item_id, 'name', v_dish.name || v_words, 'price_cents', v_cents);
end
$$;

create or replace function public.pidi_place_order(payload jsonb)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
-- Errors are short codes (MIN_FOOD, BAD_ITEM:2, SOLD_OUT:2, REST_CLOSED:taco-brava, ...). The website turns
-- each into a sentence in the customer's language, so no English text and no hours come from here.
-- Prices: a restaurant whose menu is in pidi_menu is priced from it, line by line (pidi_menu_price); the price
-- the phone sends is ignored there, and "repriced" in the answer says the phone's price was not the menu's.
-- A restaurant with no menu rows yet still takes the phone's price_cents, as before.
declare
  rest_id uuid;
  rest_partner boolean;
  food integer := 0;
  fee integer;
  minimum integer;
  dish jsonb;
  n integer;
  idx integer;
  qty integer;
  price integer;
  v_sent integer;
  v_line jsonb;
  v_name text;
  v_rest_status text;
  v_repriced boolean := false;
  pay text;
  pays integer;
  usd boolean := false;
  v_lat numeric;
  v_lng numeric;
  v_due timestamptz;
  outside boolean := false;
  local_time time;
  last_order time;
  hours text;
  token text;
  v_client text;
  existing jsonb;
  new_id uuid;
  uname text;
  digits text;
  dish_slug text;
  lines jsonb := '[]'::jsonb;
  any_partner boolean := false;
  busy integer;
  e_min integer;
  e_max integer;
  v_night integer;
  v_open integer;
  v_tonight integer;
begin
  if payload is null or jsonb_typeof(payload) <> 'object' then
    raise exception 'BAD_PAYLOAD';
  end if;

  -- A retry with the same token gets the order that already exists, whatever changed since.
  v_client := nullif(trim(coalesce(payload->>'client_token', '')), '');
  if v_client is not null then
    select public.pidi_order_public(o.id) into existing
    from public.pidi_orders o
    where o.client_token = v_client;
    if existing is not null then
      return existing;
    end if;
  end if;

  if lower(coalesce(payload->>'pickup', '')) in ('true', '1', 'yes') then
    raise exception 'DELIVERY_ONLY';
  end if;

  uname := trim(coalesce(payload->>'name', ''));
  if uname = '' or trim(coalesce(payload->>'phone', '')) = ''
     or trim(coalesce(payload->>'area', '')) = ''
     or trim(coalesce(payload->>'address', '')) = '' then
    raise exception 'MISSING';
  end if;
  digits := regexp_replace(payload->>'phone', '\D', '', 'g');
  if length(digits) < 7 or length(digits) > 15 then
    raise exception 'BAD_PHONE';
  end if;
  if length(uname) > 60 or length(payload->>'area') > 60 or length(payload->>'address') > 300
     or length(coalesce(payload->>'note', '')) > 300 then
    raise exception 'BAD_PAYLOAD';
  end if;

  if jsonb_typeof(payload->'items') is distinct from 'array' or jsonb_array_length(payload->'items') < 1 then
    raise exception 'NO_ITEMS';
  end if;
  n := jsonb_array_length(payload->'items');
  if n > 60 then
    raise exception 'BAD_PAYLOAD';
  end if;
  for idx in 0 .. n - 1
  loop
    dish := payload->'items'->idx;
    if jsonb_typeof(dish) is distinct from 'object'
       or coalesce(dish->>'qty', '') !~ '^[0-9]{1,3}$'
       or length(trim(coalesce(dish->>'name', ''))) < 1
       or length(dish->>'name') > 160
       or length(coalesce(dish->>'id', '')) > 40 then
      raise exception 'BAD_ITEM:%', idx;
    end if;
    qty := (dish->>'qty')::integer;
    if qty < 1 or qty > 20 then
      raise exception 'BAD_ITEM:%', idx;
    end if;
    v_sent := null;
    if coalesce(dish->>'price_cents', '') ~ '^[0-9]{1,6}$' then
      v_sent := (dish->>'price_cents')::integer;
    end if;
    dish_slug := lower(trim(coalesce(dish->>'restaurant', payload->>'restaurant', '')));
    select r.id, r.partner, r.menu_status into rest_id, rest_partner, v_rest_status
    from public.pidi_restaurants r
    where r.slug = dish_slug and r.active;
    -- not in the system, or "Opening soon" / hidden on the website
    if not found or coalesce(v_rest_status, 'open') <> 'open' then
      raise exception 'REST_CLOSED:%', dish_slug;
    end if;
    if exists (select 1 from public.pidi_menu m where m.restaurant_id = rest_id) then
      v_line := public.pidi_menu_price(rest_id, dish);
      if v_line ? 'error' then
        raise exception '%:%', v_line->>'error', idx;
      end if;
      price := (v_line->>'price_cents')::integer;
      v_name := v_line->>'name';
      if v_sent is not null and v_sent <> price then
        v_repriced := true;
      end if;
    else
      -- no menu here yet for this restaurant: the phone's price, as before
      if v_sent is null or v_sent > 100000 then
        raise exception 'BAD_ITEM:%', idx;
      end if;
      price := v_sent;
      v_name := trim(dish->>'name');
    end if;
    if rest_partner then
      any_partner := true;
    end if;
    food := food + qty * price;
    lines := lines || jsonb_build_array(jsonb_build_object(
      'restaurant_id', rest_id,
      'name', v_name,
      'qty', qty,
      'price_cents', price
    ));
  end loop;

  -- No minimum order (Victor, 16 Oct 2026): min_food_cents is 0, and 0 never refuses an order.
  minimum := coalesce(public.pidi_setting('min_food_cents')::integer, 0);
  if minimum > 0 and food < minimum then
    raise exception 'MIN_FOOD';
  end if;
  fee := public.pidi_delivery_fee(any_partner);

  pay := lower(trim(coalesce(payload->>'pay', '')));
  if pay = 'cash' then
    usd := lower(coalesce(payload->>'pays_in_usd', '')) in ('true', '1', 'yes');
    if usd then
      -- The driver tells the amount in US dollars at the door.
      pays := food + fee;
    else
      if coalesce(payload->>'pays_with_cents', '') !~ '^[0-9]{1,7}$' then
        raise exception 'CASH_SHORT';
      end if;
      pays := (payload->>'pays_with_cents')::integer;
      if pays < food + fee then
        raise exception 'CASH_SHORT';
      end if;
    end if;
  elsif pay = 'transfer' then
    pays := null;
  else
    raise exception 'BAD_PAY';
  end if;

  if nullif(payload->>'lat', '') is not null or nullif(payload->>'lng', '') is not null then
    if coalesce(payload->>'lat', '') !~ '^-?[0-9]{1,3}(\.[0-9]{1,10})?$'
       or coalesce(payload->>'lng', '') !~ '^-?[0-9]{1,3}(\.[0-9]{1,10})?$' then
      raise exception 'BAD_PIN';
    end if;
    v_lat := (payload->>'lat')::numeric;
    v_lng := (payload->>'lng')::numeric;
    if v_lat < -90 or v_lat > 90 or v_lng < -180 or v_lng > 180 then
      raise exception 'BAD_PIN';
    end if;
  end if;

  hours := coalesce(public.pidi_setting('hours_mode'), 'reject');
  last_order := coalesce(nullif(public.pidi_setting('last_order'), '')::time, time '01:30');
  busy := coalesce(public.pidi_setting('busy_min')::integer, 0);
  e_min := coalesce(public.pidi_setting('eta_min')::integer, 35) + busy;
  e_max := coalesce(public.pidi_setting('eta_max')::integer, 50) + busy;

  if nullif(payload->>'due_at', '') is not null then
    -- A pre-order: judged by when it must arrive, tonight between 10 PM and 1:45 AM.
    begin
      v_due := (payload->>'due_at')::timestamptz;
    exception when others then
      raise exception 'BAD_TIME';
    end;
    local_time := (v_due at time zone 'America/Aruba')::time;
    if v_due < now() + make_interval(mins => greatest(15, e_min - 25))
       or v_due > now() + interval '24 hours'
       or not (local_time >= time '22:00' or local_time <= time '01:45') then
      if hours = 'flag' then
        outside := true;
      else
        raise exception 'BAD_TIME';
      end if;
    end if;
  else
    v_due := now();
    local_time := (now() at time zone 'America/Aruba')::time;
    if not (local_time >= time '22:00' or local_time < last_order) then
      if hours = 'flag' then
        outside := true;
      else
        raise exception 'CLOSED';
      end if;
    end if;
  end if;

  -- One phone: at most a few orders waiting for the kitchen, and a few a night.
  select count(*) filter (where o.status = 'new'),
         count(*) filter (where ((o.created_at at time zone 'America/Aruba') - interval '12 hours')::date
                              = ((now() at time zone 'America/Aruba') - interval '12 hours')::date)
    into v_open, v_tonight
  from public.pidi_orders o
  where o.created_at > now() - interval '36 hours'
    and right(regexp_replace(o.phone, '\D', '', 'g'), 7) = right(digits, 7);
  if v_open >= coalesce(public.pidi_setting('max_open_per_phone')::integer, 2)
     or v_tonight >= coalesce(public.pidi_setting('max_night_per_phone')::integer, 6) then
    raise exception 'RATE_LIMIT';
  end if;

  -- A short number per service night (noon to noon, Aruba time): "Order 14". Counted by the
  -- night the order is delivered, so a pre-order placed in the morning joins tonight's numbers.
  perform pg_advisory_xact_lock(hashtext('pidi-night-no'));
  select coalesce(max(o.night_no), 0) + 1 into v_night
  from public.pidi_orders o
  where o.due_at > v_due - interval '36 hours'
    and o.due_at < v_due + interval '36 hours'
    and ((o.due_at at time zone 'America/Aruba') - interval '12 hours')::date
      = ((v_due at time zone 'America/Aruba') - interval '12 hours')::date;

  token := public.pidi_new_token();
  insert into public.pidi_orders (
    public_token, client_token, customer_name, phone, area, address,
    lat, lng, note, pay, food_cents, fee_cents, pays_with_cents, pays_in_usd, transfer_status,
    due_at, outside_hours, test, eta_min, eta_max, night_no
  ) values (
    token, v_client, uname, trim(payload->>'phone'), trim(payload->>'area'),
    trim(payload->>'address'), v_lat, v_lng, nullif(trim(coalesce(payload->>'note', '')), ''),
    pay::public.pidi_pay_method, food, fee, pays, usd,
    case when pay = 'transfer' then 'awaiting'::public.pidi_transfer_status else null end,
    v_due, outside, coalesce(lower(payload->>'test') in ('true', '1', 'yes'), false), e_min, e_max, v_night
  ) returning id into new_id;

  insert into public.pidi_order_items (order_id, restaurant_id, name, qty, price_cents)
  select new_id,
         (dish_line->>'restaurant_id')::uuid,
         dish_line->>'name',
         (dish_line->>'qty')::integer,
         (dish_line->>'price_cents')::integer
  from jsonb_array_elements(lines) dish_line;

  insert into public.pidi_order_restaurants (order_id, restaurant_id, food_cents)
  select new_id,
         (dish_line->>'restaurant_id')::uuid,
         sum((dish_line->>'qty')::integer * (dish_line->>'price_cents')::integer)
  from jsonb_array_elements(lines) dish_line
  group by (dish_line->>'restaurant_id')::uuid;

  perform public.pidi_log(new_id, 'new');
  return public.pidi_order_public(new_id) || jsonb_build_object('repriced', v_repriced);
end
$$;

-- What the website needs to promise a time: the usual window plus the kitchen's busy minutes.
create or replace function public.pidi_public_state()
returns jsonb
language sql
stable
security definer
set search_path = public, extensions
as $$
  select jsonb_build_object(
    'ok', true,
    'busy_min', coalesce(public.pidi_setting('busy_min')::integer, 0),
    'eta_min', coalesce(public.pidi_setting('eta_min')::integer, 35),
    'eta_max', coalesce(public.pidi_setting('eta_max')::integer, 50)
  )
$$;

-- The kitchen app sends one restaurant's menu here, from the website's menu.json: after signing in, when the
-- website's menu changes, and straight after a save on the Menu tile (from_save true). Orders are then priced
-- from it (pidi_menu_price). status is open / soon / hidden from site.json; null leaves it as it is. items is
-- menu.json's "items" (id, name, price, soldOut, includes, options); null leaves the dishes as they are. A dish
-- no longer on the menu is marked not listed (nothing is removed).
-- The website's copy can be about 10 minutes old (its cache), so for 15 minutes after a Menu-tile save a copy
-- read from the website (from_save false) is not taken: an older copy never undoes a newer save.
create or replace function public.pidi_kitchen_sync_menu(session text, restaurant text, status text, items jsonb, from_save boolean)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  v_rest uuid;
  v_saved timestamptz;
  v_item jsonb;
  v_id text;
  v_ids text[] := '{}';
  v_opts jsonb;
  v_incl jsonb;
begin
  if not public.pidi_kitchen_ok(session) then
    raise exception 'Sign in again.';
  end if;
  select r.id, r.menu_saved_at into v_rest, v_saved
  from public.pidi_restaurants r
  where r.slug = lower(trim(coalesce(pidi_kitchen_sync_menu.restaurant, '')))
  for update;
  if not found then
    return jsonb_build_object('ok', false, 'error', 'That restaurant is not in the order system.');
  end if;
  if pidi_kitchen_sync_menu.status is not null and pidi_kitchen_sync_menu.status not in ('open', 'soon', 'hidden') then
    raise exception 'A restaurant is open, soon or hidden.';
  end if;
  if not coalesce(from_save, false) and v_saved is not null and v_saved > now() - interval '15 minutes' then
    return jsonb_build_object('ok', true, 'skipped', true);
  end if;

  if pidi_kitchen_sync_menu.items is not null then
    if jsonb_typeof(pidi_kitchen_sync_menu.items) <> 'array'
       or jsonb_array_length(pidi_kitchen_sync_menu.items) < 1
       or jsonb_array_length(pidi_kitchen_sync_menu.items) > 200 then
      raise exception 'That menu has no dishes.';
    end if;
    for v_item in select x from jsonb_array_elements(pidi_kitchen_sync_menu.items) x
    loop
      v_id := case when jsonb_typeof(v_item) = 'object' then trim(coalesce(v_item->>'id', '')) else '' end;
      if v_id !~ '^[A-Za-z0-9_-]{1,40}$' or v_id = any(v_ids)
         or length(trim(coalesce(v_item->>'name', ''))) < 1 or length(v_item->>'name') > 160
         or coalesce(v_item->>'price', '') !~ '^[0-9]{1,6}$' or (v_item->>'price')::integer > 100000
         or jsonb_typeof(coalesce(v_item->'options', '[]'::jsonb)) <> 'array'
         or jsonb_typeof(coalesce(v_item->'includes', '[]'::jsonb)) <> 'array' then
        raise exception 'A dish on that menu can''t be read: %', left(coalesce(v_item->>'name', v_id), 60);
      end if;
      -- each option: an id, its words, one choice or many, and choices that each carry a label and a whole price
      if exists (
        select 1 from jsonb_array_elements(coalesce(v_item->'options', '[]'::jsonb)) g
        where jsonb_typeof(g) <> 'object' or jsonb_typeof(g->'choices') is distinct from 'array'
           or coalesce(g->>'id', '') = '' or coalesce(g->>'type', '') not in ('one', 'many')
           or exists (
             select 1
             from jsonb_array_elements(case when jsonb_typeof(g->'choices') = 'array' then g->'choices' else '[]'::jsonb end) c
             where jsonb_typeof(c) <> 'object' or coalesce(c->>'id', '') = '' or trim(coalesce(c->>'label', '')) = ''
                or coalesce(c->>'price', '0') !~ '^[0-9]{1,5}$'
           )
      ) then
        raise exception 'An option on that menu can''t be read: %', left(v_item->>'name', 60);
      end if;
      select coalesce(jsonb_agg(jsonb_build_object(
               'id', g->>'id',
               'label', coalesce(g->>'label', ''),
               'type', g->>'type',
               'default', g->>'default',
               'choices', (
                 select coalesce(jsonb_agg(jsonb_build_object(
                          'id', c->>'id', 'label', c->>'label', 'price', coalesce((c->>'price')::integer, 0)
                        ) order by ch.cn), '[]'::jsonb)
                 from jsonb_array_elements(g->'choices') with ordinality ch(c, cn)
               )
             ) order by og.gn), '[]'::jsonb)
        into v_opts
      from jsonb_array_elements(coalesce(v_item->'options', '[]'::jsonb)) with ordinality og(g, gn);
      select coalesce(jsonb_agg(to_jsonb(i.v)), '[]'::jsonb) into v_incl
      from jsonb_array_elements_text(coalesce(v_item->'includes', '[]'::jsonb)) i(v);
      v_ids := v_ids || v_id;
      insert into public.pidi_menu as m (restaurant_id, item_id, name, price_cents, sold_out, listed, includes, options, updated_at)
      values (v_rest, v_id, trim(v_item->>'name'), (v_item->>'price')::integer,
              lower(coalesce(v_item->>'soldOut', 'false')) in ('true', '1', 'yes'), true, v_incl, v_opts, now())
      on conflict (restaurant_id, item_id) do update
        set name = excluded.name, price_cents = excluded.price_cents, sold_out = excluded.sold_out,
            listed = true, includes = excluded.includes, options = excluded.options, updated_at = now();
    end loop;
    update public.pidi_menu m
      set listed = false, updated_at = now()
      where m.restaurant_id = v_rest and m.listed and not (m.item_id = any(v_ids));
  end if;

  update public.pidi_restaurants r
    set menu_status = coalesce(pidi_kitchen_sync_menu.status, r.menu_status),
        menu_synced_at = now(),
        menu_saved_at = case when coalesce(from_save, false) then now() else r.menu_saved_at end
    where r.id = v_rest;
  return jsonb_build_object('ok', true, 'skipped', false, 'items', coalesce(array_length(v_ids, 1), 0));
end
$$;

-- Supabase gives anon and authenticated execute on every new function by default.
-- Take that back on pidi_ functions, then grant anon only the ones the apps call.
do $pidi_grants$
declare
  sig text;
  who text;
begin
  for sig in
    select p.oid::regprocedure::text
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public' and p.proname like 'pidi\_%' escape '\'
  loop
    execute format('revoke all on function %s from public', sig);
    foreach who in array array['anon', 'authenticated'] loop
      if exists (select 1 from pg_roles where rolname = who) then
        execute format('revoke all on function %s from %I', sig, who);
      end if;
    end loop;
  end loop;
end
$pidi_grants$;

grant execute on function public.pidi_ping() to anon;
grant execute on function public.pidi_place_order(jsonb) to anon;
grant execute on function public.pidi_order_status(text) to anon;
grant execute on function public.pidi_find_order(text) to anon;
grant execute on function public.pidi_public_state() to anon;
grant execute on function public.pidi_kitchen_login(text) to anon;
grant execute on function public.pidi_kitchen_feed(text) to anon;
grant execute on function public.pidi_kitchen_accept(text, uuid) to anon;
grant execute on function public.pidi_kitchen_set_status(text, uuid, text) to anon;
grant execute on function public.pidi_kitchen_mark_ready(text, uuid, text) to anon;
grant execute on function public.pidi_kitchen_cancel(text, uuid) to anon;
grant execute on function public.pidi_kitchen_transfer_paid(text, uuid) to anon;
grant execute on function public.pidi_kitchen_set_busy(text, integer) to anon;
grant execute on function public.pidi_kitchen_sync_menu(text, text, text, jsonb, boolean) to anon;
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
grant execute on function public.pidi_admin_list_drivers(text) to anon;
grant execute on function public.pidi_admin_remove_driver(text, uuid) to anon;

commit;
