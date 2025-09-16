# The Finals (Pizza) Effect  
This project explores how finals weeks at Boston universities align with spikes in Google search interest for **“pizza near me”**. The goal was to understand how exam stress translates into demand for quick, convenient food.  

📑 Check out my [slide deck here](https://www.canva.com/design/DAGzFpATp2c/hnRAEQsEyQu5E6FmyvH8sg/view?utm_content=DAGzFpATp2c&utm_campaign=designshare&utm_medium=link2&utm_source=uniquelinks&utlId=h9dd6fcb2bb)

---

## The repo includes:
- **Scrapers**: Pull registrar/academic calendars (MIT, Harvard, BU, Tufts, UMass Boston, BC).  
- **Cleaner**: Standardizes finals calendars, fills gaps, and merges with Google Trends.  
- **Visualization Maker**: Jupyter notebook producing line charts, overlap plots, heatmaps, and event studies.

---

## Data Dictionary  

### Finals Calendars  
| Column        | Description                           | Type   |
|---------------|---------------------------------------|--------|
| school        | University name (e.g., MIT, Harvard)  | string |
| term          | Term label (Fall / Spring)            | string |
| year          | Academic year (e.g., 2025)            | int    |
| finals_start  | Start date of finals period           | date   |
| finals_end    | End date of finals period             | date   |
| source_url    | Registrar calendar source             | string |

### Google Trends (Massachusetts)  
| Column         | Description                    | Type  |
|----------------|--------------------------------|-------|
| date           | Month start (YYYY-MM-DD)       | date  |
| pizza_near_me  | Search index (0–100)           | float |
| coffee_near_me | Search index (0–100)           | float |

### Weekly Merged Dataset  
| Column                  | Description                                 | Type  |
|--------------------------|---------------------------------------------|-------|
| week_start               | Week (Mon) timestamp                        | date  |
| week_end                 | Week (Sun) timestamp                        | date  |
| finals_school_count_week | # of universities in finals that week       | int   |
| is_finals_week           | Indicator (1 = finals week, 0 = otherwise)  | int   |
| pizza_ma4                | 4-week moving average (pizza searches)      | float |
| coffee_ma4               | 4-week moving average (coffee searches)     | float |

---

## Key Insights
- **Pizza demand spikes**: Clear rise in searches during finals weeks.  
- **Pre-finals ramp**: Searches begin rising ~1 week before finals start.  
- **Overlap effect**: The more schools in finals at once, the stronger the spike.  
- **Coffee check**: Coffee searches also rise, supporting the “quick food demand” story.  

---

## How AI Helped
- Assisted with repetitive tasks like generating rolling averages and plotting templates.  
- Supported narrative framing, but **all analysis, cleaning, and interpretation were my own work**.  

---

## Sources
- [MIT Academic Calendar](https://registrar.mit.edu/calendar)  
- [Harvard FAS Calendar](https://registrar.fas.harvard.edu/calendars)  
- [BU Registrar Calendar](https://www.bu.edu/reg/calendars/semester/)  
- [Tufts Registrar Calendars](https://students.tufts.edu/registrar/calendars)  
- [UMass Boston Academic Calendar](https://www.umb.edu/registrar/academic-calendar/)  
- [Boston College Academic Calendar](https://www.bc.edu/bc-web/offices/student-services/registrar/academic-calendar.html)  
- [Google Trends – Massachusetts](https://trends.google.com) for *“pizza near me”* and *“coffee near me”*  
 

---

## Tools
- **Python**: core data collection, cleaning, and visualization
- **Pandas & NumPy**: data wrangling, feature creation (e.g., finals week flags, moving averages)
- **Matplotlib**: main visualization (line charts, heatmaps, event studies)
- **Jupyter Notebook**: exploratory analysis and figure creation 
