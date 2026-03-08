'use strict';

const db = require('@arangodb').db;

const result = db._query(`
FOR purchase IN purchase
  LET seller = FIRST(
    FOR s IN OUTBOUND purchase bought_from
      RETURN KEEP(s, '_id', '_key', 'name', 'seller_kind')
  )
  LET paymentMethod = FIRST(
    FOR method IN OUTBOUND purchase paid_via
      RETURN KEEP(method, '_id', '_key', 'provider', 'method_kind')
  )
  LET obligation = FIRST(
    FOR ob IN OUTBOUND purchase creates
      RETURN KEEP(ob, '_id', '_key', 'total_amount', 'installments', 'currency')
  )
  LET items = (
    FOR purchaseItem IN OUTBOUND purchase includes
      LET producedItems = (
        FOR item IN OUTBOUND purchaseItem results_in
          LET snapshots = (
            FOR snap IN INBOUND item describes
              RETURN KEEP(snap, '_id', '_key', 'category', 'attributes')
          )
          RETURN {
            item: KEEP(item, '_id', '_key', 'item_kind'),
            snapshots,
          }
      )
      RETURN {
        purchase_item: KEEP(purchaseItem, '_id', '_key', 'quantity', 'unit_price', 'currency'),
        produced_items: producedItems,
      }
  )
  LET settlements = (
    FOR payment IN INBOUND obligation settles
      RETURN KEEP(payment, '_id', '_key', 'amount', 'currency', 'paid_at')
  )
  RETURN {
    purchase: KEEP(purchase, '_id', '_key', 'purchased_at', 'currency', 'total_amount'),
    seller,
    payment_method: paymentMethod,
    payment_obligation: obligation,
    settlements,
    items,
  }
`);

print(JSON.stringify(result.toArray(), null, 2));
