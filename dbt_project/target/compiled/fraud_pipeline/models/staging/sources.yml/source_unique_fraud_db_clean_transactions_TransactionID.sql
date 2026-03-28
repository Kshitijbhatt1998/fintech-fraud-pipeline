
    
    

select
    TransactionID as unique_field,
    count(*) as n_records

from "fraud"."main"."clean_transactions"
where TransactionID is not null
group by TransactionID
having count(*) > 1


