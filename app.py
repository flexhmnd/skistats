from flask import Flask, render_template, request
from sqlalchemy import create_engine, text
import dash
from dash import dcc, html, Input, Output
import pandas as pd
import plotly.express as px
import os


app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')

DATABASE_URL = os.getenv("DATABASE_URL")  # this should be set in Render's environment tab
engine = create_engine(DATABASE_URL)

# Column metadata
ALL_COLUMNS = {
    "state": "State",
    "vertical_drop": "Vertical Drop (feet)",
    "base_elevation": "Base Elevation (feet)",
    "peak_elevation": "Peak Elevation (feet)",
    "slope_length": "Slope Length (miles)",
    "acreage": "Acreage (acres)",
    "snowfall": "Annual Snowfall (inches)",
    "owner": "Owner",
    "lift_total": "Total Lift Count",
    "price": "Day Ticket Price"
}

FILTER_LABELS = {
    "state": "State",
    "vertical_drop": "Vertical Drop",
    "base_elevation": "Base Elevation",
    "peak_elevation": "Peak Elevation",
    "slope_length": "Slope Length",
    "acreage": "Acreage",
    "snowfall": "Annual Snowfall",
    "owner": "Owner",
    "lift_total": "Total Lift Count",
    "price": "Day Ticket Price"
}

@app.route('/')
def index():
    # Default visible columns
    default_columns = ["state", "vertical_drop", "snowfall", "price"]

    # Check if 'columns' is in the request arguments
    if not request.args:
        selected_columns = default_columns
    else:
        selected_columns = request.args.getlist("columns")  # could be empty, and that’s okay

    # Sort options
    sort_by = request.args.get('sort_by', 'name')
    sort_order = request.args.get('sort_order', 'asc')

    if sort_by not in ['name'] + list(ALL_COLUMNS.keys()):
        sort_by = 'name'
    if sort_order not in ['asc', 'desc']:
        sort_order = 'asc'
    
    if sort_by not in selected_columns and sort_by != 'name':
        selected_columns.append(sort_by)

    nonprofit_only = request.args.get("nonprofit") == "yes"

    # Pagination (only apply if nonprofit filter not selected)
    if not nonprofit_only:
        page = int(request.args.get('page', 1))
        per_page = 100
        offset = (page - 1) * per_page
        limit_offset_clause = "LIMIT :limit OFFSET :offset"
    else:
        page = 1
        per_page = None
        offset = None
        limit_offset_clause = ""

    columns_sql = ', '.join(['name'] + selected_columns)

    where_clause = "WHERE nonprofit = 'Yes'" if nonprofit_only else ""
    query = text(f"""
        SELECT {columns_sql}
        FROM resorts
        {where_clause}
        ORDER BY {sort_by} {sort_order}
        {limit_offset_clause}
    """)

    params = {"limit": per_page, "offset": offset} if not nonprofit_only else {}

    with engine.connect() as conn:
        result = conn.execute(query, params).fetchall()


    return render_template(
        'index.html',
        resorts=result,
        page=page,
        columns=selected_columns,
        column_labels={k: v for k, v in ALL_COLUMNS.items() if k in selected_columns},
        filter_labels=FILTER_LABELS,
        all_columns=ALL_COLUMNS,
        sort_by=sort_by,
        sort_order=sort_order,
        nonprofit=nonprofit_only
    )

@app.route('/map')
def map_view():
    return render_template('map_view.html')

with engine.connect() as conn:
    df = pd.read_sql("SELECT * FROM resorts", conn)


# Create Dash app inside Flask
dash_app = dash.Dash(
    __name__,
    server=app,
    url_base_pathname='/map/',  # Dash app will be served at /map
    external_stylesheets=[
        'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap'
    ]
)

owners = sorted(df['owner'].dropna().unique())
lift_options = sorted(df['surface_lifts_only'].dropna().unique())
sort_vars = ['vertical_drop_ft', 'base_elevation_ft', 'peak_elevation_ft', 'price', 'annual_snowfall', 'slope_mi', 'skiable_acres', 'total_lifts']
sort_dict = {
    'Vertical Drop': 'vertical_drop_ft',
    'Base Elevation': 'base_elevation_ft',
    'Peak Elevation': 'peak_elevation_ft',
    'Day Ticket Price': 'price',
    'Annual Snowfall': 'annual_snowfall',
    'Slope Length': 'slope_mi',
    'Acreage': 'skiable_acres',
    'Total Lifts': 'total_lifts'
}


dash_app.layout = html.Div(style={
    'fontFamily': "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
    'margin': '0',
    'padding': '0',
    'backgroundColor': '#fafafa',
    'lineHeight': '1'  # Add this line
}, children=[
    
    # Map container with better styling
    html.Div(style={
        'position': 'relative',
        'width': '98vw',
        'height': '90vh',
        'minHeight': '500px',
        'margin': '0 auto',
        'backgroundColor': 'white',
        'borderRadius': '12px',
        'boxShadow': '0 4px 12px rgba(0, 0, 0, 0.1)',
        'overflow': 'hidden'
    }, children=[

        # Map (fills container)
        dcc.Graph(
            id='ski-map',
            style={'position': 'absolute', 'top': 0, 'left': 0, 'width': '100%', 'height': '100%'},
            config={
                'scrollZoom': True,
                'displayModeBar': False,
                'doubleClick': 'reset'
            }
        ),


        # Enhanced Filter Panel
        html.Div(className='filter-panel', style={
            'position': 'absolute',
            'top': '20px',
            'right': '20px',
            'backgroundColor': 'rgba(255, 255, 255, 0.95)',
            'backdropFilter': 'blur(10px)',
            'border': '1px solid rgba(255, 255, 255, 0.3)',
            'borderRadius': '12px',
            'padding': '20px',
            'boxShadow': '0 8px 32px rgba(0, 0, 0, 0.15)',
            'zIndex': 10,
            'width': '280px',
            'minHeight': '200px',
            'maxHeight': '80vh',
        }, children=[
            html.H3("Sort", style={
                'margin': '0 0 16px 0',
                'fontSize': '18px',
                'fontWeight': '600',
                'color': '#111'
            }),

            html.Div(style={'marginBottom': '20px'}, children=[
                html.Label("Color & Size By", style={
                    'fontSize': '14px',
                    'fontWeight': '500',
                    'color': '#555',
                    'marginBottom': '8px',
                    'display': 'block'
                }),
                dcc.Dropdown(
                    id='sort-variable',
                    options=[{'label': label, 'value': key} for label, key in sort_dict.items()],
                    value=None,
                    style={'fontSize': '14px',
                            'position': 'relative'},
                    maxHeight=400
                ),
            ]),

            html.H3("Filters", style={
                'margin': '0 0 16px 0',
                'fontSize': '18px',
                'fontWeight': '600',
                'color': '#111'
            }),
            
            html.Div(style={'marginBottom': '20px'}, children=[
                html.Label("Resort Owner", style={
                    'fontSize': '14px',
                    'fontWeight': '500',
                    'color': '#555',
                    'marginBottom': '8px',
                    'display': 'block'
                }),
                dcc.Dropdown(
                    id='owner-filter',
                    options=[{'label': o, 'value': o} for o in owners],
                    value=owners,
                    multi=True,
                    placeholder='Select owners...',
                    style={'fontSize': '14px'},
                    maxHeight=200
                )
            ]),
            
            html.Div(children=[
                html.Label("Surface Lifts Only", style={
                    'fontSize': '14px',
                    'fontWeight': '500',
                    'color': '#555',
                    'marginBottom': '8px',
                    'display': 'block'
                }),
                dcc.Dropdown(
                    id='lift-filter',
                    options=[{'label': str(o), 'value': o} for o in lift_options],
                    value=None,
                    placeholder='All lift types',
                    style={'fontSize': '14px',
                           'overflow': 'visible'
                           }
                )
            ])
            
        ]),

        html.Div(
            id='resort-count',
            style={
                'position': 'absolute',
                'top': '20px',
                'left': '20px',
                'backgroundColor': 'rgba(255, 255, 255, 0.9)',
                'backdropFilter': 'blur(10px)',
                'padding': '8px 12px',
                'borderRadius': '6px',
                'fontSize': '12px',
                'color': '#666',
                'zIndex': 10
            },
            children="Showing 0 ski resorts"
        )

    
    ])
    
])




@dash_app.callback(
    Output('ski-map', 'figure'),
    Input('owner-filter', 'value'),
    Input('lift-filter', 'value'),
    Input('sort-variable', 'value')
)
def update_map(owner, lift, sort_var):
    column_lookup = {
        'vertical_drop_ft': 'Vertical Drop (ft)',
        'base_elevation_ft': 'Base Elevation (ft)',
        'peak_elevation_ft': 'Peak Elevation (ft)',
        'price': 'Day Ticket Price ($)',
        'annual_snowfall': 'Annual Snowfall (in)',
        'slope_mi': 'Slope Length (mi)',
        'skiable_acres': 'Skiable Acres',
        'total_lifts': 'Total Lifts'
    }
    sort_label = column_lookup.get(sort_var, 'price')
    filtered_df = df.copy()
    if owner:
        filtered_df = filtered_df[filtered_df['owner'].isin(owner)]

    if lift:
        filtered_df = filtered_df[filtered_df['surface_lifts_only'] == lift]

    if sort_var:
        fig = px.scatter_mapbox(
            filtered_df,
            lat='latitude',
            lon='longitude',
            hover_name='name',
            hover_data={
                'state': True,
                'owner': True,
                sort_var: True,
                'latitude': False,
                'longitude': False
            },
            color=sort_var,
            size=sort_var,
            size_max=20,
            color_continuous_scale='Viridis',
            zoom=3,
            height=None,
            title=""
        )
    else:
        fig = px.scatter_mapbox(
            filtered_df,
            lat='latitude',
            lon='longitude',
            hover_name='name',
            hover_data={
                'state': True,
                'owner': True,
                'latitude': False,
                'longitude': False
            },
            zoom=3,
            height=None,
            title=""
        )

        # Manually set a uniform color
        fig.update_traces(marker=dict(color='#8396ff', size=5))


    fig.update_layout(
        mapbox=dict(
            style='carto-positron',
            center=dict(lat=45, lon=-100),
            zoom=3
        ),
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        font=dict(
            family="Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
            size=12,
            color="#111"
        ),
        coloraxis=dict(
            colorbar=dict(
                title=dict(text=sort_label, font=dict(size=12)),
                len=0.6,
                thickness=15,
                bgcolor='rgba(255,255,255,0.9)',
                x=0.02,
                y=0.02,
                xanchor='left',
                yanchor='bottom',
                outlinewidth=1,
                outlinecolor='rgba(0,0,0,0.1)',
                borderwidth=1,
                bordercolor='rgba(0,0,0,0.1)'
            )
        ),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )

    return fig

@dash_app.callback(
    Output('resort-count', 'children'),
    Input('owner-filter', 'value'),
    Input('lift-filter', 'value'),
)
def update_resort_count(owner, lift):
    filtered_df = df.copy()
    if owner:
        filtered_df = filtered_df[filtered_df['owner'].isin(owner)]
    if lift:
        filtered_df = filtered_df[filtered_df['surface_lifts_only'] == lift]
    return f"Showing {len(filtered_df)} ski resorts"


@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/feedback')
def feedback():
    return render_template('feedback.html')

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    name = request.form.get('name')
    message = request.form.get('feedback')
    print(f"Feedback from {name or 'Anonymous'}: {message}")
    return render_template('submitted_feedback.html')



if __name__ == '__main__':
    app.run(debug=True)
