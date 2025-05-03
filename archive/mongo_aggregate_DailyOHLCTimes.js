db.getCollection('OHLC_EUR_USD_S5').aggregate(
  [
    {
      $facet: {
        highs: [
          { $sort: { high: -1 } },
          {
            $group: {
              _id: {
                $dateToString: {
                  format: '%Y-%m-%d',
                  date: '$timestamp'
                }
              },
              highestHigh: { $max: '$high' },
              highestHighSample: {
                $first: '$$ROOT'
              }
            }
          }
        ],
        lows: [
            { $sort: { low: 1 } },
            {
              $group: {
                _id: {
                  $dateToString: {
                    format: '%Y-%m-%d',
                    date: '$timestamp'
                  }
                },
                lowestLow: { $min: '$low' },
                lowestLowSample: { $first: '$$ROOT' }
              }
            }
          ],
        opensCloses: [
          { $sort: { timestamp: 1 } },
          {
            $group: {
              _id: {
                $dateToString: {
                  format: '%Y-%m-%d',
                  date: '$timestamp'
                }
              },
              firstOpen: { $first: '$$ROOT' },
              lastClose: { $last: '$$ROOT' }
            }
          }
        ]
      }
    },
    {
      $project: {
        bar: {
          $setUnion: [
            '$highs',
            '$lows',
            '$opensCloses'
          ]
        }
      }
    },
    { $unwind: { path: '$bar' } },
    {
      $group: {
        _id: '$bar._id',
        open: { $max: '$bar.firstOpen.open' },
        high: { $max: '$bar.highestHigh' },
        low: { $max: '$bar.lowestLow' },
        close: { $max: '$bar.lastClose.close' },
        highTimestamp: {
          $max: '$bar.highestHighSample.timestamp'
        },
        lowTimestamp: {
          $max: '$bar.lowestLowSample.timestamp'
        }
      }
    }
  ],
  { maxTimeMS: 60000, allowDiskUse: true }
);


db.createCollection("OHLC_EUR_USD_S5");
db.OHLC_EUR_USD_S5.createIndex( { timestamp: 1 }, {unique: true });
