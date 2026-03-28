
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select grain
from "fraud"."main"."fraud_summary"
where grain is null



  
  
      
    ) dbt_internal_test