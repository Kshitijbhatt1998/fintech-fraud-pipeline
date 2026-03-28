
    
    

select
    transaction_id as unique_field,
    count(*) as n_records

from "fraud"."main"."fraud_features"
where transaction_id is not null
group by transaction_id
having count(*) > 1


