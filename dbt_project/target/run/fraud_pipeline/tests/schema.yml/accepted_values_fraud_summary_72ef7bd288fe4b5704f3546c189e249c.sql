
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

with all_values as (

    select
        grain as value_field,
        count(*) as n_records

    from "fraud"."main"."fraud_summary"
    group by grain

)

select *
from all_values
where value_field not in (
    'daily','product','card_type','email_domain','hour_of_day'
)



  
  
      
    ) dbt_internal_test