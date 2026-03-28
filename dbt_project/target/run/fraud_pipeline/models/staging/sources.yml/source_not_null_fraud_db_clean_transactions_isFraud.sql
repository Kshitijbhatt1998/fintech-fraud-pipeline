
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select isFraud
from "fraud"."main"."clean_transactions"
where isFraud is null



  
  
      
    ) dbt_internal_test