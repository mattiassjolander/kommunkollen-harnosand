# Redaktionen kan fastställa partitillhörighet per period

ADR-0004 tar en ledamots parti ur protokollet vid varje sammanträde. I praktiken saknar många närvarolistor parti, och när protokollet anger fel parti eller har lästs fel måste varje förekomst rättas för sig. Partibyten är sällsynta, så samma rättelse upprepas vid sammanträde efter sammanträde.

Redaktionen kan därför fastställa en persons parti under en period: ett parti eller partilös ("-"), från och med ett datum och till och med ett datum eller tills vidare, med en motivering. Perioden gäller personen, alltså alla namnvarianter som slagits ihop, och sammanträden vars datum ligger inom perioden. Sammanträden utan datum omfattas inte. Den går igenom samma flöde som en rättelse (ADR-0002): utkast, granskad och publicerad, och en utgivare som inte registrerade perioden godkänner den. En granskad eller publicerad period ändras genom en ny version och kan återkallas. Två publicerade perioder för samma person får inte överlappa. Det kontrolleras när perioden registreras och när den publiceras, och en ny version jämförs inte med den den ersätter.

Ordningen för vad som gäller vid ett sammanträde är: en publicerad rättelse av just den förekomsten, en publicerad period, protokollets uppgift, och sist ett härlett parti. Gäller en period härleds inget parti. Perioden gäller närvarolistan, den som en ersättare tjänstgör för, voteringslistorna (även den som ersätts), yrkanden, reservationer och motionärer. Registret och filtret på parti räknar med partiet som gäller.

Protokollets uppgift ändras inte och finns kvar som underlag. När perioden ändrar partiet som protokollet anger markeras det "Fastställt av redaktionen", och läsaren kan se vad protokollet anger, perioden och motiveringen. Anger protokollet samma parti som perioden visas ingen markering. Personsidan visar de publicerade perioderna och, som underlag, partiet över tid som protokollen anger det.

Detta kompletterar ADR-0004 och ersätter den inte: partiet är fortfarande belagt i protokollet där protokollet anger det, och där redaktionen gjort en annan bedömning syns det.
