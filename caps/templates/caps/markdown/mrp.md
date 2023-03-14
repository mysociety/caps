# How our local polling data is calculated

## How does MRP polling work?

If you want to know what people in the local area think about something, you want to do several things:

* Survey enough people in that area to build up a reasonable picture of responses (roughly 200 people),
* Either make sure you're asking a representative group in the first place, or adjust the result afterwards based on what you know about who lives in an area of the area.

For instance, if you know than half of the people who live in an area are women, but they make up two-thirds of the people you surveyed, you would want to adjust the result to account for that.

The trouble is if you want to build a local picture *everywhere*, you would need to survey hundreds of thousands of people. This quickly becomes very expensive.

A method called [MRP (Multilevel regression and post stratification)](https://en.wikipedia.org/wiki/Multilevel_regression_with_poststratification) tries to solve this problem another way. MRP polling is an approach that assumes that, generally, constituencies and local authorities are really different from each other in that they have different mixes of demographic groups.

This means if you do a national survey of a few thousand people, have a good picture of different demographic groups and the intersections, and then also have a very good picture of the different mixes in different places, you can use maths to get a pretty good picture of what a poll in every local area would look like, at a fraction of the cost.

## Local adjusting of national polls

One way of thinking about this is that you are doing a local adjustment of national polls.

If we had a national poll that said 80% were in support of wind farms, you might reasonably ask *"but is that the same in this specific rural area?"*. The next step you'd take is to look and see if respondents who lived in rural areas felt differently, and having figured that out, you might also want to understand the difference because of the age profile of the area. This process is effectively doing all that work upfront: *“Based on what we know about the kind of people in this area, here is how we have adjusted the national result”.* 

This means MRP polling can answer a key question people working at the local level have about national polling: *Is my local area different, or is it just like the rest of the country?* 

## How are the local results shown on this site calculated?

On this site we are readjusting MRP polls calculated for Parliamentary constituencies to local authorities. The two polls we are using are from [PublicFirst](https://www.publicfirst.co.uk/new-public-first-polling-for-onward.html) and [Survation](https://www.survation.com/polling-in-every-constituency-in-britain-shows-strong-support-for-building-wind-farms-to-drive-down-consumer-bills/).

We can do this because local authorities are larger than constituencies. Knowing the population in each constituency, we can add these up and convert the percentage of people in individual constituencies who agree with a statement to a percentage of the population of the local authority who would agree with the statement. 

The big complication is that while generally constituencies do not cross multiple local authorities, enough do this problem needs to be addressed.

One approach is to split the constituency into several parts so that each part is only in one local authority. We split the population of a constituency between these parts by using the known population of neighbourhood-sized census areas, divided that population among all postcodes in that small area, and then adding up the results of all postcodes in each local authority.

Once you have worked this out for lower-tier and unitary local authorities, you can go through the same process to calculate percentages for county councils, and combined authorities. 

Our recalculated polling results [are available to download](https://pages.mysociety.org/climate_mrp_polling/).