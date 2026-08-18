select
    animal_id,
    life_number,
    herd_id,
    birth_date
from {{ source('raw', 'animals') }}
