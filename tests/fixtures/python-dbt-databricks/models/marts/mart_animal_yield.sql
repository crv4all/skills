{{ config(materialized='incremental', unique_key='animal_id') }}

select
    a.animal_id,
    a.life_number,
    count(l.lactation_id) as lactation_count
from {{ ref('stg_animals') }} a
left join {{ ref('stg_lactations') }} l on l.animal_id = a.animal_id
group by 1, 2
