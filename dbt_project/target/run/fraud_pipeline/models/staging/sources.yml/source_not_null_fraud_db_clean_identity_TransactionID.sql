
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select TransactionID
from "fraud"."main"."clean_identity"
where TransactionID is null



  
  
      
    ) dbt_internal_test