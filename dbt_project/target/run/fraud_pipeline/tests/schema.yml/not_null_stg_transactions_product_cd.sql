
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select product_cd
from "fraud"."main"."stg_transactions"
where product_cd is null



  
  
      
    ) dbt_internal_test