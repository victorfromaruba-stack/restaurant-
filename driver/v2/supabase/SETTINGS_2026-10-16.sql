-- Victor's decisions of 16 Oct 2026, for a database set up before them. Paste all of it into the Supabase
-- SQL editor of the Pidi project and press Run. Safe to run twice. In any other project it stops at the first
-- check and changes nothing.
--   No minimum order: min_food_cents 0 (0 never refuses an order).
--   Delivery 35 to 50 minutes: eta_min 35, eta_max 50 (the kitchen's busy minutes still add on top).
-- Orders already placed keep the times they were promised. The last lines show the three values.

begin;

-- Stops here, changing nothing, when this isn't the Pidi database.
do $guard$ begin
  if to_regclass('public.pidi_orders') is null or to_regclass('public.pidi_settings') is null then
    raise exception 'This is not the Pidi database (no pidi_orders table). Nothing was changed.';
  end if;
end $guard$;

-- A database that never had one of these keys gets it here; the updates below then set the value.
insert into public.pidi_settings (key, value) values
  ('min_food_cents', '0'),
  ('eta_min', '35'),
  ('eta_max', '50')
on conflict (key) do nothing;

update public.pidi_settings set value = '0' where key = 'min_food_cents';
update public.pidi_settings set value = '35' where key = 'eta_min';
update public.pidi_settings set value = '50' where key = 'eta_max';

commit;

select key, value from public.pidi_settings where key in ('min_food_cents', 'eta_min', 'eta_max') order by key;
