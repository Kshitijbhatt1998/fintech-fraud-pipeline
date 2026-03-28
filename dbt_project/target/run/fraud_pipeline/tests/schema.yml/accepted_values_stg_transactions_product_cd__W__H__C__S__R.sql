
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

with all_values as (

    select
        product_cd as value_field,
        count(*) as n_records

    from "fraud"."main"."stg_transactions"
    group by product_cd

)

select *
from all_values
where value_field not in (
    'W','H','C','S','R'
)



  
  
      
    ) dbt_internal_test