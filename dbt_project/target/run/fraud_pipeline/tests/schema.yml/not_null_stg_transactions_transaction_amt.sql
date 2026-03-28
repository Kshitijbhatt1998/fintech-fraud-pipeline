
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select transaction_amt
from "fraud"."main"."stg_transactions"
where transaction_amt is null



  
  
      
    ) dbt_internal_test