
    
    

with all_values as (

    select
        isFraud as value_field,
        count(*) as n_records

    from "fraud"."main"."clean_transactions"
    group by isFraud

)

select *
from all_values
where value_field not in (
    '0','1'
)


