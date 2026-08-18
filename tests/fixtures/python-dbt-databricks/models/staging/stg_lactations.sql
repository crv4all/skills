-- Trap: raw.lactations is not declared in models/sources.yml.
select
    lactation_id,
    animal_id,
    calving_date,
    dry_off_date
from {{ source('raw', 'lactations') }}
